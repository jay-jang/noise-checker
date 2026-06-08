"""검사 엔진 (M2-B) — 릴리스 아티팩트 로드 + 텍스트 검사 파이프라인.

docs/03-architecture.md §2(텍스트 검사 파이프라인·위험도 정책표 v1)을 구현한다.
엔진은 DB를 직접 읽지 않고 빌드계가 만든 **릴리스 아티팩트**(terms.json /
manifest.json / kiwi_user_dict.tsv)만 로드한다 (03 §1, 07 비노출 정책).

파이프라인 단계 (각 단계 on/off 가능, 단계별 소요시간을 debug에 기록):
  단계 0  정규화      normalize(원문) -> (norm_text, src_offset)
  단계 1a AC 스캔     active surface + verified 변형의 normalized_key 오토마톤 1회 스캔
  단계 1b 자모 경계   매치 경계가 음절 자모 이음새를 가르면 폐기
                      (jamo/chosung/pattern 변형은 자모 단위가 정상이므로 예외)
  단계 1c 형태소 경계  Kiwi 토큰 경계와 대조 — 매치가 더 긴 토큰의 내부 부분문자열이면 폐기
  단계 1d safe_context ±20자 창에 safe context 토큰이 있으면 ambiguous/common 매치 해소
  단계 2  패턴/조합    term_kind='pattern' 정규식 + term_kind='number' combination_rules 평가
  단계 4  위험도 산정  정책표 v1 적용 → usage_recommendation / risk_score

엔진 인터페이스 계약(noise_checker.engine):
  Engine.load(artifact_dir) -> Engine    # normalizer 버전 불일치 시 ValueError
  engine.check(text) -> dict
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ahocorasick
from kiwipiepy import Kiwi

from noise_checker import normalizer

__all__ = ["Engine", "compiled_normalizer_version"]


def compiled_normalizer_version() -> str:
    """코드 측 normalizer 버전을 읽는다.

    M2-A(빌더)가 `NORMALIZER_VERSION`을 추가하면 그것을, 아니면 기존
    `NORMALIZER_CODE_VERSION`을, 둘 다 없으면 "1"을 쓴다 (머지 충돌 방지 —
    계약: getattr(normalizer, "NORMALIZER_VERSION", ...)).
    """
    version = getattr(normalizer, "NORMALIZER_VERSION", None)
    if version is not None:
        return str(version)
    return str(getattr(normalizer, "NORMALIZER_CODE_VERSION", "1"))


# 자모 단위 매칭이 정상이라 음절 경계 필터에서 예외 처리할 변형 종류 (03 §2 단계1).
_JAMO_LEVEL_KINDS = frozenset({"jamo", "chosung", "pattern"})

# chosung 변형 match_confidence (03 §2 정책표 — chosung은 본질 lossy라
# skip-char 0.8보다 보수적인 0.7, 단독 매칭 위험 잔존으로 상한 review 고정).
_CHOSUNG_CONFIDENCE = 0.7

# safe_context 탐색 창 (매치 전후 원문 ±N자).
_SAFE_CONTEXT_WINDOW = 20

# --- M2 인용 휴리스틱 (정책표 적용 직전, M3 문맥분류 도입 전의 규칙 기반 보수 장치) ---
# 보도/연구/대항표현이 혐오어를 인용·메타 논의하는 문장을 revise로 과잉 권고하지
# 않도록, 인용 신호가 있으면 usage_recommendation을 review로 상한한다(매치 제거 아님 —
# 자문 포지셔닝상 인용 보도도 검토 가치는 있으므로 review까지는 유지).
_QUOTATION_WINDOW = 15
# 따옴표류: 매치가 이 문자쌍 사이에 감싸여 있으면 인용으로 본다.
_QUOTE_OPENERS = "'\"'\"「『‘“"
_QUOTE_CLOSERS = "'\"'\"」』’”"
_QUOTE_CHARS = frozenset(_QUOTE_OPENERS + _QUOTE_CLOSERS)
# 메타담론 토큰: ±15자 창에 있으면 용어를 가리키는 메타 논의로 본다.
# '모욕'은 제외한다 — 혐오 행위 서술('…모욕하는 게시물')과 메타 인용을 가르는 경계어휘.
_METADISCOURSE_TOKENS = (
    "표현", "멸칭", "용어", "단어", "혐오 표현", "차별", "비하",
    "보도", "보고서", "강의", "논문", "기사", "비판", "사례", "인용",
)

# --- M2 skip-char 창 스캔 -----------------------------------------------------
# 한글 음절 사이에 삽입된 단일 구분자를 제거한 2차 뷰에서 AC 재스캔(03 §2 정책표 0.8).
_SKIP_SEPARATORS = frozenset(". \t\n\r·ㆍ•-_*~,")
# 연속 구분자 허용 상한(‘한\n남’·‘좌. 좀’류 2연속까지만 — 오탐 방지).
_SKIP_MAX_RUN = 2
_SKIP_CONFIDENCE = 0.8


@dataclass(frozen=True)
class _Entry:
    """오토마톤 키 하나에 대응하는 사전 항목 메타데이터.

    하나의 normalized_key가 여러 term(동철 충돌)에 매핑될 수 있으므로 AC payload는
    (key, [entry...]) 형태로 저장한다.
    """

    term_id: int
    surface: str
    term_kind: str
    severity: int
    ambiguity: str
    status: str
    categories: tuple[str, ...]
    safe_contexts: tuple[str, ...]
    is_dogwhistle_marker: bool
    combination_rules: tuple[dict[str, Any], ...]
    # 이 키가 verified 변형이면 그 종류, exact surface면 None.
    variant_kind: str | None


@dataclass
class _Match:
    """파이프라인 내부 매치 표현 (원문 오프셋 기준)."""

    start: int  # 원문 코드포인트 시작
    end: int  # 원문 코드포인트 끝(배타)
    norm_start: int  # 정규화 텍스트 시작
    norm_end: int  # 정규화 텍스트 끝(배타)
    entry: _Entry
    match_confidence: float
    matched_text: str
    flags: list[str] = field(default_factory=list)
    # 정책표 산정 시 revise→review로 상한할지(인용 휴리스틱·공백 결합 skip-char).
    cap_review: bool = False


class Engine:
    """릴리스 아티팩트를 로드해 텍스트를 검사하는 엔진."""

    def __init__(
        self,
        *,
        release_version: str,
        automaton: ahocorasick.Automaton,
        pattern_entries: list[tuple[re.Pattern[str], _Entry, tuple[str, ...]]],
        kiwi: Kiwi,
    ) -> None:
        self.release_version = release_version
        self._automaton = automaton
        self._pattern_entries = pattern_entries
        self._kiwi = kiwi
        # 사용자 사전 없는 기본 Kiwi — 경계 재검(단계 1c')에서 lazy 1회 생성.
        self._base_kiwi: Kiwi | None = None

    # ---- 로드 ---------------------------------------------------------------
    @classmethod
    def load(cls, artifact_dir: str | Path) -> Engine:
        """아티팩트 디렉토리에서 엔진을 구성한다.

        manifest.normalizer_code_version이 코드 normalizer 버전과 불일치하면
        ValueError로 로드를 거부한다 (07 §7 — 버전 불일치 = 미탐 방지).
        """
        adir = Path(artifact_dir)
        manifest = json.loads((adir / "manifest.json").read_text(encoding="utf-8"))

        manifest_version = str(manifest.get("normalizer_code_version", ""))
        code_version = compiled_normalizer_version()
        if manifest_version != code_version:
            raise ValueError(
                "normalizer 버전 불일치로 아티팩트 로드 거부 — "
                f"manifest={manifest_version!r} code={code_version!r}"
            )

        terms = json.loads((adir / "terms.json").read_text(encoding="utf-8"))

        automaton = ahocorasick.Automaton()
        # normalized_key -> [_Entry...] (동철 충돌 대응)
        key_entries: dict[str, list[_Entry]] = {}
        pattern_entries: list[tuple[re.Pattern[str], _Entry, tuple[str, ...]]] = []

        for t in terms:
            entry_common = {
                "term_id": int(t["term_id"]),
                "surface": t["surface"],
                "term_kind": t["term_kind"],
                "severity": int(t["severity"]),
                "ambiguity": t["ambiguity"],
                "status": t["status"],
                "categories": tuple(t.get("categories", [])),
                "safe_contexts": tuple(t.get("safe_contexts", [])),
                "is_dogwhistle_marker": bool(t.get("is_dogwhistle_marker", False)),
                "combination_rules": tuple(t.get("combination_rules", [])),
            }

            if t["term_kind"] == "pattern":
                # pattern은 정규식 경로로 분리 컴파일. 정규식은 별도 pattern 필드
                # (아티팩트 계약 v1.1)에서 읽고, 없으면 surface를 리터럴로 escape해
                # 폴백한다(구버전 아티팩트 안전망 — 매치에 fallback 플래그 기록).
                regex = t.get("pattern")
                fallback = regex is None
                compiled = re.compile(regex if regex is not None else re.escape(t["surface"]))
                pattern_flags = ["pattern_fallback_literal"] if fallback else []
                pattern_entries.append(
                    (
                        compiled,
                        _Entry(variant_kind="pattern", **entry_common),
                        tuple(pattern_flags),
                    )
                )
                continue

            # exact surface
            key_entries.setdefault(t["normalized_key"], []).append(
                _Entry(variant_kind=None, **entry_common)
            )
            # verified 변형 (terms.json에는 verified만 적재됨)
            for v in t.get("variants", []):
                key_entries.setdefault(v["normalized_key"], []).append(
                    _Entry(variant_kind=v["variant_kind"], **entry_common)
                )

        for key, entries in key_entries.items():
            automaton.add_word(key, (key, entries))
        automaton.make_automaton()

        kiwi = _build_kiwi(adir / "kiwi_user_dict.tsv")

        return cls(
            release_version=str(manifest["release_version"]),
            automaton=automaton,
            pattern_entries=pattern_entries,
            kiwi=kiwi,
        )

    # ---- 검사 ---------------------------------------------------------------
    def check(self, text: str, *, stages: dict[str, bool] | None = None) -> dict[str, Any]:
        """텍스트를 검사해 계약 형식의 결과 dict를 반환한다.

        stages로 단계별 on/off 가능 (기본 전부 on). 디버그 필드에 단계별
        소요시간(ms)을 기록한다.
        """
        cfg = _stage_config(stages)
        timings: dict[str, float] = {}

        # 단계 0 — 정규화 (오프셋 매핑 포함)
        with _timed(timings, "normalize"):
            norm_text, src_offset = normalizer.normalize(text)

        # 단계 1a — AC 스캔
        with _timed(timings, "ac_scan"):
            matches = self._ac_scan(text, norm_text, src_offset)

        # 단계 1a' — skip-char 창 스캔 (음절 사이 단일 구분자 제거 뷰 재스캔)
        if cfg["skip_char"]:
            with _timed(timings, "skip_char"):
                matches.extend(self._skip_char_scan(text, norm_text, src_offset, matches))

        # 단계 1b — 자모 경계 필터
        if cfg["jamo_boundary"]:
            with _timed(timings, "jamo_boundary"):
                matches = [m for m in matches if _jamo_boundary_ok(m, src_offset, len(norm_text))]

        # 단계 1c — Kiwi 형태소 경계 검사
        if cfg["morpheme_boundary"]:
            with _timed(timings, "morpheme_boundary"):
                matches = self._morpheme_filter(text, matches)

        # 단계 1d — safe_contexts 필터 (전 매치 스팬을 창에서 마스킹 — 반복 표기 대응)
        if cfg["safe_context"]:
            with _timed(timings, "safe_context"):
                spans = [(m.start, m.end) for m in matches]
                matches = [
                    m for m in matches if not _safe_context_resolves(m, text, spans)
                ]

        # 단계 2 — 패턴/조합 매칭
        if cfg["pattern"]:
            with _timed(timings, "pattern"):
                pattern_matches = self._pattern_scan(text)
                # pattern 매치도 safe_contexts 해소 대상 (예: '~노'는 경상도 방언
                # 의문 종결어미와 동형 — 방언 토큰이 창에 있으면 해소). 단계 1d가
                # AC 스캔 전에 끝나 pattern 매치를 못 보므로 여기서 동일 필터를 적용한다.
                if cfg["safe_context"]:
                    pattern_matches = [
                        m for m in pattern_matches if not _safe_context_resolves(m, text)
                    ]
                matches.extend(pattern_matches)
        if cfg["combination"]:
            with _timed(timings, "combination"):
                _apply_combination_rules(matches, text)

        # 단계 3' — 인용·메타담론 휴리스틱 (정책표 적용 직전, M3 문맥분류 전 보수 장치)
        if cfg["quotation"]:
            with _timed(timings, "quotation"):
                for m in matches:
                    if _quotation_context(m, text):
                        m.cap_review = True
                        m.flags.append("quotation_heuristic")

        # 단계 4 — 위험도 산정 + 응답 조립
        with _timed(timings, "scoring"):
            result_matches = [_score_match(m) for m in matches]
            result_matches.sort(key=lambda r: (r["span"]["start"], r["span"]["end"]))
            overall = _overall_recommendation(result_matches)

        return {
            "release_version": self.release_version,
            "overall_recommendation": overall,
            "matches": result_matches,
            "debug": {"stage_timings_ms": timings, "match_count": len(result_matches)},
        }

    # ---- 단계 구현 ----------------------------------------------------------
    def _ac_scan(self, text: str, norm_text: str, src_offset: list[int]) -> list[_Match]:
        """오토마톤 1회 스캔. 정규화 좌표 매치를 원문 좌표로 환원한다."""
        out: list[_Match] = []
        nn = len(norm_text)
        for end_idx, (key, entries) in self._automaton.iter(norm_text):
            norm_start = end_idx - len(key) + 1
            norm_end = end_idx + 1
            # 원문 좌표 환원: src_offset으로 시작/끝 음절 경계 복원.
            src_start = src_offset[norm_start]
            last_src = src_offset[norm_end - 1]
            src_end = last_src + 1
            # 같은 원문 문자에서 시작된 자모를 모두 포함하도록 norm_end를 확장(음절 정렬).
            while norm_end < nn and src_offset[norm_end] == last_src:
                norm_end += 1
            for entry in entries:
                out.append(self._make_variant_match(
                    entry, src_start, src_end, norm_start, norm_end,
                    text[src_start:src_end],
                ))
        return out

    @staticmethod
    def _make_variant_match(
        entry: _Entry,
        src_start: int,
        src_end: int,
        norm_start: int,
        norm_end: int,
        matched_text: str,
    ) -> _Match:
        """AC 매치 1건을 변형 종류별 confidence/상한으로 _Match로 만든다.

        exact surface 1.0 / leet 등 검증 변형 0.9 / chosung 0.7(본질 lossy).
        chosung은 단독 매칭 위험이 남아 상한 review(cap_review)·flag 'chosung_variant'.
        """
        if entry.variant_kind is None:
            return _Match(
                start=src_start, end=src_end, norm_start=norm_start, norm_end=norm_end,
                entry=entry, match_confidence=1.0, matched_text=matched_text,
            )
        if entry.variant_kind == "chosung":
            return _Match(
                start=src_start, end=src_end, norm_start=norm_start, norm_end=norm_end,
                entry=entry, match_confidence=_CHOSUNG_CONFIDENCE,
                matched_text=matched_text,
                flags=["chosung_variant"], cap_review=True,
            )
        return _Match(
            start=src_start, end=src_end, norm_start=norm_start, norm_end=norm_end,
            entry=entry, match_confidence=0.9, matched_text=matched_text,
        )

    def _morpheme_filter(self, text: str, matches: list[_Match]) -> list[_Match]:
        """Kiwi 형태소 경계 검사 (문장당 1회 분석, 03 §2 단계0/1).

        매치가 더 긴 단일 토큰의 **내부 부분문자열**이면(경계 불일치) 폐기한다.
        예: '운지버섯'은 한 토큰 → 그 안의 '운지' 매치 제거.
        pattern/number 매치는 형태소 단위가 아니므로 검사하지 않는다.
        """
        if not matches:
            return matches
        # 토큰 경계 집합 (start, end) — 원문 코드포인트 기준.
        token_spans = [(t.start, t.start + t.len) for t in self._kiwi.tokenize(text)]
        kept: list[_Match] = []
        for m in matches:
            if m.entry.term_kind in ("pattern", "number"):
                kept.append(m)
                continue
            if _within_larger_token(m.start, m.end, token_spans):
                continue
            if self._boundary_recheck_drops(text, m):
                continue
            kept.append(m)
        return kept

    def _boundary_recheck_drops(self, text: str, m: _Match) -> bool:
        """사용자 사전 부스트가 경계 검사를 무력화하는 경우를 기본 Kiwi로 재검한다.

        word 매치의 직전/직후 원문 문자가 한글이면, 사용자 사전이 없는 기본 Kiwi로
        해당 텍스트를 재분석한다. 그 한글에 인접한 매치 경계가 기본 Kiwi 토큰 내부를
        가로지르면(토큰 경계에 정렬되지 않으면) 매치를 폐기한다. 예:
          - '노무'(부스트) → '노무라'를 노무+라로 쪼개나, 기본 Kiwi는 '노무라' 한
            토큰 → 끝 경계가 토큰 내부 → drop.
          - '삼일한'(부스트) → '삼일한약방'에서 끝 경계가 기본 '한약방' 토큰 내부 → drop.
        '노무한 박수'·'된장녀라니'처럼 인접 음절이 별도 토큰/조사로 분석돼 매치 경계가
        토큰 경계에 정렬되면 살린다(미탐 방지).
        """
        if m.entry.term_kind != "word":
            return False
        before = text[m.start - 1] if m.start > 0 else ""
        after = text[m.end] if m.end < len(text) else ""
        before_hangul = _is_hangul_syllable(before)
        after_hangul = _is_hangul_syllable(after)
        if not (before_hangul or after_hangul):
            return False
        base = self._get_base_kiwi()
        cutting = [
            t for t in base.tokenize(text)
            if (before_hangul and t.start < m.start < t.start + t.len)
            or (after_hangul and t.start < m.end < t.start + t.len)
        ]
        if not cutting:
            return False
        # 가로지른 토큰이 전부 OOV(기본 사전에 없는 신조어)면 폐기하지 않는다 —
        # '응디시티'(파생 멸칭)·'오또케오또케'(중첩 조롱)처럼 비하 파생어 내부
        # 매치일 가능성이 높다. 경계가 불확실하므로 상한 review로 보수 처리.
        # 사전어('노무라' NNP, '한약방' NNG) 침범은 종전대로 폐기(오탐 방지).
        if all(t.oov for t in cutting):
            m.cap_review = True
            m.flags.append("oov_boundary_kept")
            return False
        m.flags.append("boundary_recheck_dropped")
        return True

    def _get_base_kiwi(self) -> Kiwi:
        """사용자 사전 없는 기본 Kiwi (경계 재검 전용) — lazy 1회 생성."""
        if self._base_kiwi is None:
            self._base_kiwi = Kiwi()
        return self._base_kiwi

    def _skip_char_scan(
        self,
        text: str,
        norm_text: str,
        src_offset: list[int],
        exact_matches: list[_Match],
    ) -> list[_Match]:
        """음절 사이 단일 구분자를 제거한 2차 뷰에서 AC 재스캔(03 §2 정책표 0.8).

        정규화(자모) 텍스트에서 한글 자모 사이에 낀 구분자 run(≤2자)을 제거한
        skip 뷰를 만들고(원문 오프셋 유지), 그 위에서 오토마톤을 1회 스캔한다.
        동일 span에 exact/변형 매치가 이미 있으면 중복 제거한다. 구분자에 공백이
        포함된 결합 매치는 일반 문장 오탐을 막기 위해 ambiguity 무관 상한 review로
        제한한다(`space_split 결합 매치는 revise 금지` 불변식).
        """
        skip_text, skip_to_norm, joined_has_space = _build_skip_view(norm_text)
        if skip_text == norm_text:
            return []  # 제거된 구분자 없음 — exact 스캔과 동일하므로 생략.
        existing_spans = {(m.start, m.end) for m in exact_matches}
        out: list[_Match] = []
        nn = len(norm_text)
        for end_idx, (key, entries) in self._automaton.iter(skip_text):
            sk_start = end_idx - len(key) + 1
            sk_end = end_idx + 1
            # skip 좌표 → 원래 정규화 좌표
            norm_start = skip_to_norm[sk_start]
            norm_end = skip_to_norm[sk_end - 1] + 1
            # 결합 구간이 실제로 구분자를 가로질렀을 때만 skip-char 후보(아니면 exact가 잡음).
            if norm_end - norm_start == len(key):
                continue
            src_start = src_offset[norm_start]
            last_src = src_offset[norm_end - 1]
            src_end = last_src + 1
            while norm_end < nn and src_offset[norm_end] == last_src:
                norm_end += 1
            if (src_start, src_end) in existing_spans:
                continue
            spans_space = any(
                joined_has_space[i] for i in range(sk_start, sk_end - 1)
            )
            for entry in entries:
                if entry.variant_kind is not None:
                    continue  # skip-char는 exact surface 키에만 적용(변형 중첩 방지).
                out.append(
                    _Match(
                        start=src_start,
                        end=src_end,
                        norm_start=norm_start,
                        norm_end=norm_end,
                        entry=entry,
                        match_confidence=_SKIP_CONFIDENCE,
                        matched_text=text[src_start:src_end],
                        flags=["skip_char"],
                        cap_review=spans_space,
                    )
                )
        return out

    def _pattern_scan(self, text: str) -> list[_Match]:
        """term_kind='pattern' 정규식 매칭 (원문에 직접 적용)."""
        out: list[_Match] = []
        for pat, entry, pattern_flags in self._pattern_entries:
            for mo in pat.finditer(text):
                out.append(
                    _Match(
                        start=mo.start(),
                        end=mo.end(),
                        norm_start=mo.start(),
                        norm_end=mo.end(),
                        entry=entry,
                        match_confidence=1.0,
                        matched_text=mo.group(0),
                        flags=list(pattern_flags),
                    )
                )
        return out


# --- Kiwi 로드 --------------------------------------------------------------
def _build_kiwi(user_dict_path: Path) -> Kiwi:
    """Kiwi 인스턴스 + 아티팩트의 사용자 사전 로드.

    사용자 사전(active surface+verified 변형)을 등록해 형태소 오분해로 경계
    필터가 무력화되는 것을 방지한다 (05 M2, 교차 리뷰 C-C1).
    """
    kiwi = Kiwi()
    if user_dict_path.exists():
        for line in user_dict_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            form = parts[0].strip()
            tag = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "NNP"
            if form:
                kiwi.add_user_word(form, tag)
    return kiwi


# --- 단계 1b: 자모 경계 ------------------------------------------------------
def _jamo_boundary_ok(m: _Match, src_offset: list[int], norm_len: int) -> bool:
    """매치 경계가 음절 자모 이음새를 가르지 않는지 검사 (03 §2 단계1).

    음절 경계는 src_offset 값이 바뀌는 지점이다. 매치 시작이 원문 문자 경계에
    정렬되고(시작 자모가 그 원문 문자의 첫 자모) 끝도 원문 문자 경계에 정렬되면
    유효. 종성→다음 초성 이음새를 가로지르는 부분 매치(예: '전주' 안의 'ㄴㅈ')는
    폐기한다.

    예외: jamo/chosung/pattern 변형은 자모 단위 매칭이 정상이므로 통과.
    """
    if m.entry.variant_kind in _JAMO_LEVEL_KINDS:
        return True
    s, e = m.norm_start, m.norm_end
    start_ok = s == 0 or src_offset[s] != src_offset[s - 1]
    end_ok = e >= norm_len or src_offset[e] != src_offset[e - 1]
    return start_ok and end_ok


# --- 단계 1c: 형태소 경계 ----------------------------------------------------
def _within_larger_token(start: int, end: int, token_spans: list[tuple[int, int]]) -> bool:
    """매치 [start,end)가 어떤 단일 토큰의 **진부분문자열**인지 검사.

    매치 구간이 한 토큰 안에 완전히 들어가면서 그 토큰보다 짧으면(경계 불일치)
    True (= 더 긴 단어의 내부 → 폐기 대상).
    """
    return any(
        ts <= start and end <= te and (te - ts) > (end - start) for ts, te in token_spans
    )


# --- 단계 1d: safe_contexts --------------------------------------------------
def _safe_context_resolves(
    m: _Match, text: str, all_spans: list[tuple[int, int]] | None = None
) -> bool:
    """ambiguous/common 매치 주변 ±20자에 safe context 토큰이 있으면 해소(True).

    unambiguous 항목은 safe_context로 해소하지 않는다 (일반어 충돌이 없으므로).

    exact/변형 매치의 창에서는 **매치 스팬(자신 + 동일 창의 다른 매치들)을 제외**
    한다 — surface가 safe 토큰을 내포하면(예: '된장녀'의 safe_contexts에 '된장')
    매치 텍스트 안의 '된장'이 자기 매치를 셀프 해소하고, '된장녀된장녀'처럼 같은
    용어가 반복되면 서로의 스팬 속 '된장'이 상대를 해소해 둘 다 미탐되는 버그를
    막는다. 경계가 우연히 결합해 safe 토큰을 오인하지 않도록 NUL로 마스킹한다.
    pattern 매치(예: '~노')는 매치 텍스트가 사용자 작성 문장 전체(greedy .+)라
    safe 토큰이 스팬 내부에 정상 출현하므로 스팬을 제외하지 않고 전체 창을 본다.
    """
    if m.entry.ambiguity == "unambiguous":
        return False
    if not m.entry.safe_contexts:
        return False
    lo = max(0, m.start - _SAFE_CONTEXT_WINDOW)
    hi = min(len(text), m.end + _SAFE_CONTEXT_WINDOW)
    if m.entry.term_kind == "pattern":
        window = text[lo:hi]
    else:
        chars = list(text[lo:hi])
        for s, e in all_spans or [(m.start, m.end)]:
            for i in range(max(s, lo), min(e, hi)):
                chars[i - lo] = "\x00"
        window = "".join(chars)
    return any(tok and tok in window for tok in m.entry.safe_contexts)


# --- 단계 1a': skip-char 뷰 --------------------------------------------------
def _is_jamo(ch: str) -> bool:
    """호환 자모(정규화 후 음절 표현)인지."""
    return bool(ch) and "ㄱ" <= ch <= "ㅣ"


def _is_hangul_syllable(ch: str) -> bool:
    """완성형 한글 음절(원문 문자)인지."""
    return bool(ch) and "가" <= ch <= "힣"


def _build_skip_view(norm_text: str) -> tuple[str, list[int], list[bool]]:
    """정규화 텍스트에서 자모 사이 구분자 run(≤2자)을 제거한 skip 뷰를 만든다.

    Returns:
        (skip_text, skip_to_norm, joined_has_space)
        skip_to_norm[i] = skip_text의 i번째 문자의 원래 norm_text 인덱스.
        joined_has_space[i] = skip_text의 i와 i+1 사이에서 제거된 run에 공백이
        있었는지(공백 결합 매치 식별용).
    """
    skip_chars: list[str] = []
    skip_to_norm: list[int] = []
    joined_has_space: list[bool] = []
    n = len(norm_text)
    i = 0
    while i < n:
        ch = norm_text[i]
        # 자모 뒤에 구분자 run이 오고 그 다음이 다시 자모면 run을 건너뛴다.
        if _is_jamo(ch) and i + 1 < n and norm_text[i + 1] in _SKIP_SEPARATORS:
            j = i + 1
            while j < n and norm_text[j] in _SKIP_SEPARATORS:
                j += 1
            run = norm_text[i + 1:j]
            if len(run) <= _SKIP_MAX_RUN and j < n and _is_jamo(norm_text[j]):
                skip_chars.append(ch)
                skip_to_norm.append(i)
                joined_has_space.append(any(c.isspace() for c in run))
                i = j
                continue
        skip_chars.append(ch)
        skip_to_norm.append(i)
        joined_has_space.append(False)
        i += 1
    return "".join(skip_chars), skip_to_norm, joined_has_space


# --- 단계 3': 인용·메타담론 휴리스틱 -----------------------------------------
def _quotation_context(m: _Match, text: str) -> bool:
    """매치가 인용/메타 논의 맥락에 있으면 True (정책표 상한 review 대상).

    (a) 매치가 따옴표류로 직접 감싸여 있거나, (b) ±15자 창에 메타담론 토큰이
    있으면 인용으로 본다. M3 문맥분류 도입 전의 규칙 기반 보수 장치이며 매치를
    제거하지 않고 등급만 상한한다(자문 포지셔닝).
    """
    before = text[m.start - 1] if m.start > 0 else ""
    after = text[m.end] if m.end < len(text) else ""
    if before in _QUOTE_CHARS and after in _QUOTE_CHARS:
        return True
    lo = max(0, m.start - _QUOTATION_WINDOW)
    hi = min(len(text), m.end + _QUOTATION_WINDOW)
    window = text[lo:m.start] + text[m.end:hi]
    return any(tok in window for tok in _METADISCOURSE_TOKENS)


# --- 단계 2: 조합 규칙 -------------------------------------------------------
def _apply_combination_rules(matches: list[_Match], text: str) -> None:
    """term_kind='number' 매치의 combination_rules 충족 여부를 평가한다.

    충족 시 in-place로 flag('composite_satisfied')를, 미충족이면
    flag('composite_unsatisfied')를 단다 — 미충족 number는 정책표대로 monitor.
    규칙 형식(아티팩트 계약): {"trigger_kind","trigger_pattern"?,"trigger_terms"?}.
    """
    matched_term_ids = {m.entry.term_id for m in matches}
    for m in matches:
        if m.entry.term_kind != "number":
            continue
        if not m.entry.combination_rules:
            m.flags.append("composite_unsatisfied")
            continue
        satisfied = any(
            _combination_rule_holds(rule, text, matched_term_ids)
            for rule in m.entry.combination_rules
        )
        m.flags.append("composite_satisfied" if satisfied else "composite_unsatisfied")


def _combination_rule_holds(
    rule: dict[str, Any], text: str, matched_term_ids: set[int]
) -> bool:
    """단일 combination_rule 충족 여부.

    trigger_pattern(정규식, date/amount/time 맥락)이 있으면 원문에 매칭되는지,
    trigger_terms(co_occurrence)가 있으면 그 term이 같은 입력에 매칭됐는지 본다.
    """
    pattern = rule.get("trigger_pattern")
    if pattern and re.search(pattern, text):
        return True
    trigger_terms = rule.get("trigger_terms") or []
    return any(tid in matched_term_ids for tid in trigger_terms)


# --- 단계 4: 위험도 정책표 v1 ------------------------------------------------
def _context_score(entry: _Entry) -> float:
    """context_score: unambiguous=1.0 / 그 외 0.5 고정(M3 전, 03 §2)."""
    return 1.0 if entry.ambiguity == "unambiguous" else 0.5


def _usage_recommendation(
    entry: _Entry, risk_score: float, *, composite_unsatisfied: bool, cap_review: bool
) -> str:
    """정책표 v1 (03 §2 단계4) — 조건 순서·불변식을 모두 보존한다.

    정책표의 행은 두 종류다:
      - **고정 monitor 행**(watchlist / composite 미충족 number): 항상 monitor.
        불변식 ②(watchlist는 항상 monitor)·'그 외 매칭(composite 미충족) → monitor'.
        monitor는 최저 등급이므로 어떤 상한도 이를 끌어올리지 못한다 → 우선 처리.
      - **상한 review 행**(도그휘슬 / ambiguity != unambiguous / M2 인용 휴리스틱·
        공백 결합 skip-char): 사다리 결과를 review_recommended로 **상한**한다
        (revise 금지 — 불변식 ①).

    base 사다리: severity≥4 AND risk≥0.7 → revise / risk≥0.35 → review / 그 외 monitor.
    cap_review는 인용 휴리스틱(단계 3')·공백 결합 skip-char가 세운 상한 신호로,
    severity 5 unambiguous(삼일한 등)이어도 revise를 review로 끌어내린다.
    """
    # 고정 monitor (불변식 — 상한이 끌어올리지 못함)
    if entry.status == "watchlist":
        return "monitor"
    if composite_unsatisfied:
        return "monitor"

    # base 사다리
    if entry.severity >= 4 and risk_score >= 0.7:
        base = "revise_recommended"
    elif risk_score >= 0.35:
        base = "review_recommended"
    else:
        base = "monitor"

    # 상한 review (도그휘슬·ambiguity·M2 인용/공백결합): revise → review로 캡
    capped = entry.is_dogwhistle_marker or entry.ambiguity != "unambiguous" or cap_review
    if capped and base == "revise_recommended":
        return "review_recommended"
    return base


def _score_match(m: _Match) -> dict[str, Any]:
    """매치 하나를 정책표 v1로 채점해 응답 항목 dict로 변환한다."""
    entry = m.entry
    context_score = _context_score(entry)
    risk_score = (entry.severity / 5) * m.match_confidence * context_score
    composite_unsatisfied = "composite_unsatisfied" in m.flags
    recommendation = _usage_recommendation(
        entry, risk_score, composite_unsatisfied=composite_unsatisfied, cap_review=m.cap_review
    )
    return {
        "span": {"start": m.start, "end": m.end},
        "matched_text": m.matched_text,
        "surface": entry.surface,
        "term_id": entry.term_id,
        "categories": list(entry.categories),
        "severity": entry.severity,
        "ambiguity": entry.ambiguity,
        "match_confidence": m.match_confidence,
        "context_score": context_score,
        "risk_score": risk_score,
        "usage_recommendation": recommendation,
        "flags": list(m.flags),
    }


_RECOMMENDATION_RANK = {
    "none": 0,
    "monitor": 1,
    "review_recommended": 2,
    "revise_recommended": 3,
}


def _overall_recommendation(result_matches: list[dict[str, Any]]) -> str:
    """매칭들의 최고 등급. 매칭 없으면 none."""
    if not result_matches:
        return "none"
    return max(
        (r["usage_recommendation"] for r in result_matches),
        key=lambda rec: _RECOMMENDATION_RANK[rec],
    )


# --- 보조 -------------------------------------------------------------------
class _timed:
    """with 블록 소요시간(ms)을 timings dict에 기록하는 컨텍스트 매니저."""

    def __init__(self, timings: dict[str, float], name: str) -> None:
        self._timings = timings
        self._name = name

    def __enter__(self) -> _timed:
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self._timings[self._name] = (time.perf_counter() - self._t0) * 1000.0


_DEFAULT_STAGES = {
    "skip_char": True,
    "jamo_boundary": True,
    "morpheme_boundary": True,
    "safe_context": True,
    "pattern": True,
    "combination": True,
    "quotation": True,
}


def _stage_config(stages: dict[str, bool] | None) -> dict[str, bool]:
    cfg = dict(_DEFAULT_STAGES)
    if stages:
        cfg.update(stages)
    return cfg
