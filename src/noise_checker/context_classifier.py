"""문맥 분류기 (M3) — 동음이의어가 위험 의미로 쓰였는지 판별하는 경량 분류기.

이 환경(CPU 4코어·GPU 없음·torch/transformers 미설치)에서 KcELECTRA→ONNX 풀
파인튜닝은 비현실적이라(docs/05 M3), 1차 분류기는 **순수 numpy 로지스틱 회귀**로
구현한다. 피처(문자 n-gram·단어 unigram 해싱 + 보조 피처)는 학습·추론이 반드시
동일해야 하므로 이 모듈에 한 번만 정의하고 scripts/train_context_classifier.py가
재사용한다(학습/서빙 피처 불일치 방지).

KcELECTRA→ONNX는 동일 인터페이스(load→score(text, surface)∈[0,1])를 유지한 채
GPU 단계 과제로 남긴다 — 엔진은 이 인터페이스에만 의존하므로 분류기 교체 시
engine.py 변경이 불필요하다.

런타임 계약(noise_checker.context_classifier):
  ContextClassifier.load(path) -> ContextClassifier   # 가중치 JSON 로드
  clf.score(text, surface) -> float                   # harmful 확률 ∈ [0,1]
추론은 순수 numpy(런타임 sklearn/scipy 불요·결정적).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

__all__ = [
    "ContextClassifier",
    "FEATURE_VERSION",
    "extract_features",
    "feature_dim",
]

# 피처 스펙 버전 — 가중치 JSON에 기록하고 로드 시 대조한다(학습/추론 피처 동기화).
FEATURE_VERSION = "ctx-feat-1"

# 해시 트릭 차원 (2^18). 문자 n-gram·단어 unigram이 같은 공간에 해싱되며
# 네임스페이스 접두로 충돌을 줄인다(아래 _hash_index).
_HASH_BITS = 18
_HASH_DIM = 1 << _HASH_BITS
_HASH_MASK = _HASH_DIM - 1

# 보조(수작업) 피처 — 해시 공간 뒤에 고정 슬롯으로 붙인다(03 §2 단계3·인용 휴리스틱과
# 정합: safe_context·따옴표·메타담론 신호는 benign 방향, 직접 비하 어조는 harmful 방향).
# engine._METADISCOURSE_TOKENS와 의미상 겹치되, 분류기는 학습으로 가중치를 정한다.
_META_TOKENS = (
    "표현", "멸칭", "용어", "단어", "혐오", "차별", "비하",
    "보도", "보고서", "강의", "논문", "기사", "비판", "사례", "인용", "담론", "분석",
)
# 대항표현(counterspeech) 신호 — benign 방향.
_COUNTER_TOKENS = (
    "규탄", "반대", "낙인", "멈춰", "쓰지 말", "차별이", "혐오라", "용인", "비판받",
)
# 직접 비하 어조 신호 — harmful 방향.
_DEROG_TOKENS = (
    "한심", "꼴", "역겹", "재수없", "병신", "주제에", "수준", "같은 것",
)
_QUOTE_CHARS = frozenset("'\"'\"「』『」‘’“”")

_AUX_NAMES = (
    "meta_token",       # 메타담론 토큰 등장 (benign)
    "counter_token",    # 대항표현 토큰 등장 (benign)
    "derog_token",      # 직접 비하 토큰 등장 (harmful)
    "quoted_surface",   # surface가 따옴표로 감싸임 (benign 경향)
    "surface_repeat",   # surface가 2회 이상 반복 (강조 → harmful 경향)
)
_AUX_DIM = len(_AUX_NAMES)


def feature_dim() -> int:
    """전체 피처 차원 (해시 공간 + 보조 피처)."""
    return _HASH_DIM + _AUX_DIM


def _hash_index(namespace: str, token: str) -> int:
    """네임스페이스+토큰을 해시 공간 인덱스로 (결정적 — 표준 hashlib 미사용,
    파이썬 hash 무작위화 영향 없는 자체 FNV-1a 변형)."""
    h = 2166136261
    for ch in namespace + "\x1f" + token:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h & _HASH_MASK


def _char_ngrams(text: str, n: int) -> list[str]:
    if len(text) < n:
        return [text] if text else []
    return [text[i:i + n] for i in range(len(text) - n + 1)]


def _word_unigrams(text: str) -> list[str]:
    return [w for w in text.split() if w]


def extract_features(text: str, surface: str) -> dict[int, float]:
    """텍스트+surface에서 희소 피처(index->value)를 추출한다(학습·추론 공용).

    - 문자 n-gram(2,3) 해싱: 공백을 _로 치환해 어절 경계를 보존.
    - 단어 unigram 해싱.
    - surface 자체를 별도 네임스페이스로(동음이의 표면 식별).
    - 보조 피처(safe/메타/대항/비하 신호, 따옴표, 반복, bias).
    값은 등장 빈도(해시 충돌·반복어 가중) — 추론 시 동일하게 계산된다.
    """
    feats: dict[int, float] = {}

    def bump(idx: int, val: float = 1.0) -> None:
        feats[idx] = feats.get(idx, 0.0) + val

    norm = text.replace("\n", " ").strip()
    spaced = norm.replace(" ", "_")
    for n in (2, 3):
        for g in _char_ngrams(spaced, n):
            bump(_hash_index(f"c{n}", g))
    for w in _word_unigrams(norm):
        bump(_hash_index("w", w))
    # 매치 surface 자체 (동음이의어 식별 신호 — 가중치가 surface별 base를 학습).
    bump(_hash_index("surf", surface))

    # 보조 피처 (해시 공간 뒤 고정 슬롯).
    base = _HASH_DIM
    aux = dict.fromkeys(range(_AUX_DIM), 0.0)
    if any(tok in norm for tok in _META_TOKENS):
        aux[0] = 1.0
    if any(tok in norm for tok in _COUNTER_TOKENS):
        aux[1] = 1.0
    if any(tok in norm for tok in _DEROG_TOKENS):
        aux[2] = 1.0
    aux[3] = float(_surface_quoted(norm, surface))
    aux[4] = float(norm.count(surface) >= 2)
    for j, v in aux.items():
        if v:
            feats[base + j] = v
    return feats


def _surface_quoted(text: str, surface: str) -> bool:
    """surface 출현 위치가 따옴표류로 감싸여 있으면 True."""
    idx = text.find(surface)
    while idx != -1:
        before = text[idx - 1] if idx > 0 else ""
        after = text[idx + len(surface)] if idx + len(surface) < len(text) else ""
        if before in _QUOTE_CHARS and after in _QUOTE_CHARS:
            return True
        idx = text.find(surface, idx + 1)
    return False


def _sigmoid(z: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-z))


class ContextClassifier:
    """학습된 로지스틱 회귀 가중치를 로드해 harmful 확률을 추론하는 분류기.

    가중치는 희소(0이 아닌 차원만) JSON으로 저장한다 — 해시 공간 2^18 전체를 덤프하면
    JSON이 수 MB가 되므로. 추론은 추출 피처 인덱스에 해당하는 가중치만 내적한다.
    """

    def __init__(
        self,
        *,
        weights: dict[int, float],
        bias: float,
        temperature: float,
        feature_version: str,
    ) -> None:
        self._weights = weights
        self._bias = bias
        self._temperature = temperature
        self._feature_version = feature_version

    @classmethod
    def load(cls, path: str | Path) -> ContextClassifier:
        """가중치 JSON에서 분류기를 구성한다.

        feature_version이 코드의 FEATURE_VERSION과 다르면 학습/추론 피처 불일치이므로
        ValueError로 거부한다(미탐·오탐 방지 — 엔진 로드의 normalizer 버전 게이트와 동형).
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        fv = data.get("feature_version")
        if fv != FEATURE_VERSION:
            raise ValueError(
                "context_classifier 피처 버전 불일치 — "
                f"model={fv!r} code={FEATURE_VERSION!r}"
            )
        weights = {int(k): float(v) for k, v in data["weights"].items()}
        return cls(
            weights=weights,
            bias=float(data["bias"]),
            temperature=float(data.get("temperature", 1.0)),
            feature_version=fv,
        )

    def score(self, text: str, surface: str) -> float:
        """harmful 확률 ∈ [0,1]. 결정적(동일 입력 → 동일 출력)."""
        feats = extract_features(text, surface)
        z = self._bias
        w = self._weights
        for idx, val in feats.items():
            wi = w.get(idx)
            if wi is not None:
                z += wi * val
        return float(_sigmoid(z / self._temperature))
