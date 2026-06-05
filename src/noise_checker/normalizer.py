"""정규화 모듈 — 검사 경로와 사전 빌드가 공유하는 단일 소스.

docs/02-database-design.md §4 (정규화 키 규약), §4.1 (오프셋 매핑),
§4.2 (키 충돌 정책)을 구현한다.

정규화 단계 (사전 빌드와 검사 API가 **반드시 동일 코드**를 import):
  1. 유니코드 NFKC 정규화 (전각/호환 문자 통일)
  2. 라틴 소문자화
  3. 한글 음절 → 호환 자모(Compatibility Jamo, U+3131~) 분해
     (예: '운지' → 'ㅇㅜㄴㅈㅣ') — 자모 분리 변형과 동일 키로 수렴
  4. 제로폭 문자·결합 기호 제거

검사 경로(`normalize`)는 (norm_text, src_offset)을 반환한다.
  src_offset[i] = norm_text의 i번째 코드포인트가 유래한 **원문** 코드포인트 인덱스.
사전 빌드(`normalized_key`)는 동일 결과 문자열만 반환한다(offset 불필요).

외부 의존성 금지 — 표준 라이브러리(unicodedata)만 사용한다.
"""

from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path

__all__ = [
    "normalize",
    "normalized_key",
    "NORMALIZER_CODE_VERSION",
    "NORMALIZER_VERSION",
]

# 정규화 로직의 의미 버전 (manifest.normalizer_code_version에 기록).
# 엔진(M2-B)은 로드 시 manifest 값과 이 상수를 대조해 불일치면 로드를 거부한다.
# 정규화 단계(NFKC→소문자→자모분해→제거)의 의미가 바뀌면 이 값을 올린다.
NORMALIZER_VERSION: str = "1.0.0"


# --- 단계 3: 한글 자모 → 호환 자모(U+3131~U+3163) 매핑 -----------------------
#
# NFKC는 호환 자모(예: 'ㅅ' U+3145)를 결합용 자모(conjoining, U+1109)로
# 변환하고, 한글 음절('운')의 NFD 분해도 결합용 자모(초성/중성/종성)를
# 만든다. 두 경로 모두 결합용 자모로 수렴하므로, 결합용 자모를 호환 자모로
# 되돌리면 표면형이 다른 입력('ㅅㅂ' vs '시발'의 자모)이 같은 키로 모인다.
#
# 핵심: 같은 음소의 초성/종성(예: 초성 ㄴ U+1102, 종성 ㄴ U+11AB)이 **같은**
# 호환 자모(ㄴ U+3134)로 수렴해야 'ㅅㅂ' 류 변형과 키가 일치한다.
# 이는 유니코드 이름('HANGUL LETTER NIEUN' vs 'HANGUL CHOSEONG/JONGSEONG
# NIEUN')의 음소 부분이 일치하므로 이름 기반 매핑으로 보장된다.


def _build_conjoining_to_compat() -> dict[str, str]:
    # 호환 자모(U+3131~U+3163): 'HANGUL LETTER <PHONEME>'
    compat: dict[str, str] = {}
    for cp in range(0x3131, 0x3164):
        name = unicodedata.name(chr(cp), "")
        if not name:
            continue
        phoneme = name.replace("HANGUL LETTER ", "")
        compat[phoneme] = chr(cp)

    # 결합용 자모(초성/중성/종성)를 음소 이름으로 호환 자모에 연결
    mapping: dict[str, str] = {}
    for label in ("CHOSEONG", "JUNGSEONG", "JONGSEONG"):
        prefix = f"HANGUL {label} "
        for cp in range(0x1100, 0x1200):
            ch = chr(cp)
            name = unicodedata.name(ch, "")
            if label not in name:
                continue
            phoneme = name.replace(prefix, "")
            target = compat.get(phoneme)
            if target is not None:
                mapping[ch] = target
    return mapping


_CONJOINING_TO_COMPAT: dict[str, str] = _build_conjoining_to_compat()

# 한글 음절 영역
_SYLLABLE_START = 0xAC00
_SYLLABLE_END = 0xD7A3

# --- 단계 4: 제거 대상 제로폭 / 포맷 문자 ------------------------------------
# 결합 기호(combining class != 0)는 unicodedata.combining()으로 일괄 제거하고,
# combining class가 0이지만 폭이 없는 포맷 문자는 아래 집합으로 명시 제거한다.
_ZERO_WIDTH: frozenset[str] = frozenset(
    {
        "​",  # ZERO WIDTH SPACE
        "‌",  # ZERO WIDTH NON-JOINER
        "‍",  # ZERO WIDTH JOINER
        "﻿",  # ZERO WIDTH NO-BREAK SPACE (BOM)
        "­",  # SOFT HYPHEN
        "⁠",  # WORD JOINER
        "᠎",  # MONGOLIAN VOWEL SEPARATOR
        "‎",  # LEFT-TO-RIGHT MARK
        "‏",  # RIGHT-TO-LEFT MARK
    }
)


def _nfkc_with_offsets(text: str) -> tuple[str, list[int]]:
    """오프셋을 보존하는 NFKC.

    NFKC는 1→N(예: '㎏'→'kg')·N→1(예: 'e'+◌́→'é') 모두 가능하므로 단순
    코드포인트 대응이 불가능하다. 그러나 NFKC는 **시작 문자(starter,
    combining class 0) + 뒤따르는 결합 문자**로 이루어진 cluster 경계를
    넘지 않는다. cluster 단위로 NFKC를 적용하면 전체 문자열 NFKC와 동일한
    결과를 얻으면서, cluster의 모든 출력 코드포인트를 그 cluster의 시작
    원문 인덱스에 귀속시킬 수 있다.

    한 cluster 안의 결합 문자는 단계 4에서 어차피 제거되므로, cluster 출력
    전부를 시작 인덱스에 귀속해도 최종 오프셋 정확도에 영향이 없다.
    """
    out_chars: list[str] = []
    out_offsets: list[int] = []

    i = 0
    n = len(text)
    while i < n:
        start = i
        i += 1
        # 시작 문자에 뒤따르는 결합 문자들을 같은 cluster로 묶는다.
        while i < n and unicodedata.combining(text[i]) != 0:
            i += 1
        cluster = text[start:i]
        for ch in unicodedata.normalize("NFKC", cluster):
            out_chars.append(ch)
            out_offsets.append(start)
    return "".join(out_chars), out_offsets


def _lower_with_offsets(
    chars: list[str], offsets: list[int]
) -> tuple[list[str], list[int]]:
    """라틴 소문자화. str.lower()는 1→N(예: 'İ'→'i̇')일 수 있으므로 코드포인트
    단위로 처리하며 각 출력 코드포인트는 원본 인덱스를 상속한다."""
    out_chars: list[str] = []
    out_offsets: list[int] = []
    for ch, off in zip(chars, offsets, strict=True):
        for low in ch.lower():
            out_chars.append(low)
            out_offsets.append(off)
    return out_chars, out_offsets


def _decompose_hangul_with_offsets(
    chars: list[str], offsets: list[int]
) -> tuple[list[str], list[int]]:
    """한글 음절을 호환 자모로 분해(1→N, 같은 원문 인덱스 N회 반복)하고,
    결합용 단독 자모를 호환 자모로 수렴시킨다."""
    out_chars: list[str] = []
    out_offsets: list[int] = []
    for ch, off in zip(chars, offsets, strict=True):
        cp = ord(ch)
        if _SYLLABLE_START <= cp <= _SYLLABLE_END:
            # 음절 → 결합용 자모(NFD) → 호환 자모
            for jamo in unicodedata.normalize("NFD", ch):
                out_chars.append(_CONJOINING_TO_COMPAT.get(jamo, jamo))
                out_offsets.append(off)
        else:
            # NFKC 후 단독 결합용 자모로 남은 경우(예: 'ㅅㅂ')도 호환 자모로 수렴
            out_chars.append(_CONJOINING_TO_COMPAT.get(ch, ch))
            out_offsets.append(off)
    return out_chars, out_offsets


def _strip_marks_with_offsets(
    chars: list[str], offsets: list[int]
) -> tuple[list[str], list[int]]:
    """제로폭 문자·결합 기호 제거(항목 제거 → 오프셋 항목도 제거)."""
    out_chars: list[str] = []
    out_offsets: list[int] = []
    for ch, off in zip(chars, offsets, strict=True):
        if ch in _ZERO_WIDTH:
            continue
        if unicodedata.combining(ch) != 0:
            continue
        out_chars.append(ch)
        out_offsets.append(off)
    return out_chars, out_offsets


def normalize(text: str) -> tuple[str, list[int]]:
    """검사 경로용 정규화.

    Returns:
        (norm_text, src_offset) — src_offset[i]는 norm_text의 i번째
        코드포인트가 유래한 원문 코드포인트 인덱스. src_offset은 단조
        비감소이며 len(src_offset) == len(norm_text).
    """
    if not text:
        return "", []

    # 단계 1: NFKC (오프셋 보존)
    s1, off1 = _nfkc_with_offsets(text)
    chars = list(s1)

    # 단계 2: 라틴 소문자화
    chars, off2 = _lower_with_offsets(chars, off1)

    # 단계 3: 한글 음절 → 호환 자모 분해
    chars, off3 = _decompose_hangul_with_offsets(chars, off2)

    # 단계 4: 제로폭 문자·결합 기호 제거
    chars, off4 = _strip_marks_with_offsets(chars, off3)

    return "".join(chars), off4


def normalized_key(text: str) -> str:
    """사전 빌드용 정규화 키 — `normalize(text)[0]`과 동일 문자열을 반환한다
    (offset 불필요). §3.2 `term.normalized_key`에 저장되는 값."""
    return normalize(text)[0]


# --- NORMALIZER_CODE_VERSION (02 §3.10 manifest 검증용) ----------------------
# 이 모듈 소스 내용 기반 해시. API 로드 시 manifest의 normalizer_code_version과
# 불일치하면 로드를 거부한다(버전 불일치 = 미탐 방지).
NORMALIZER_CODE_VERSION: str = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
