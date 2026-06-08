"""verified 변형 생성·분류 도구 (M2).

active 용어 surface마다 `variants.generate_variants`를 적용해 변형을 만들고,
다음 두 게이트로 적재 여부를 분류한다(출처가 아닌 **결정성+오탐**이 게이트다):

  1. 왕복(매칭 가능) 불변식 — kind별 정의:
       - jamo: normalizer 수렴으로 surface와 **같은** normalized_key (AC 1차 매칭).
       - leet/chosung: 자기 자신의 normalized_key(비어 있지 않고 결정적)로
         별도 term_variant 행으로 매칭(수렴 불요, variants 모듈 docstring §정규화 정합).
     이 불변식이 깨진 변형(키가 비거나, jamo인데 surface 키와 불일치)은 버그 →
     제외하고 로그.
  2. 오탐(FP) 시뮬 — 변형의 normalized_key가 일반어 코퍼스
     (`variant_fp_sim.COMMON_WORDS`)의 normalized_key와 충돌하면 unsafe.

분류 규칙(임무 명세):
  - jamo:   왕복OK + FP-safe → verified.
  - leet:   왕복OK + FP-safe → verified.
  - chosung: 초성 길이 ≥3 AND FP-safe → verified + context_required=true
             (단독 매칭 위험 잔존). 초성 길이 ≤2 → reject
             (reports/variant-fp-sim-v1.md: 2자 키 80% 일반어 충돌).

출력:
  - data/variants/verified-2026-06-08.json — 전 변형 분류 결과(reject 포함, reason).
  - reports/variant-fp-sim-v2.md — active 용어 기준 종류별·길이별 충돌 통계 + 카운트.

운영 DB에 쓰지 않는다 — 분류 결과 파일만 만든다(적재는 메인 세션).
외부 의존성 금지 — 표준 라이브러리 + noise_checker + scripts.variant_fp_sim만 사용.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.variant_fp_sim import COMMON_WORDS

from noise_checker.normalizer import normalized_key
from noise_checker.variants import generate_variants

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "data" / "variants" / "verified-2026-06-08.json"
REPORT_PATH = REPO_ROOT / "reports" / "variant-fp-sim-v2.md"

# chosung 단독 매칭 안전 초성 길이 하한 (reports v1: 2자 키 80.2% 일반어 충돌).
CHOSUNG_MIN_LEN = 3


@dataclass(frozen=True)
class Classified:
    """변형 한 건의 분류 결과."""

    surface: str
    term_id: int
    variant: str
    variant_kind: str
    normalized_key: str
    context_required: bool
    decision: str  # "verified" | "reject"
    reason: str


def _common_key_index() -> dict[str, list[str]]:
    """일반어 normalized_key → [일반어들] 색인 (FP 충돌 판정용)."""
    index: dict[str, list[str]] = defaultdict(list)
    for w in COMMON_WORDS:
        index[normalized_key(w)].append(w)
    return index


def _roundtrip_ok(kind: str, variant_key: str, surface_key: str) -> tuple[bool, str]:
    """kind별 왕복(매칭 가능) 불변식 검사.

    jamo는 surface 키로 수렴해야 하고(AC 1차 매칭), leet/chosung은 자기
    normalized_key(비어 있지 않음)로 별도 행 매칭한다(variants 모듈 docstring).
    """
    if not variant_key:
        return False, "normalized_key가 비어 매칭 불가(버그)"
    if kind == "jamo" and variant_key != surface_key:
        return False, "jamo가 surface 키로 수렴하지 않음(정규화 정합 버그)"
    return True, ""


def _classify_variant(
    surface: str,
    term_id: int,
    variant: str,
    kind: str,
    surface_key: str,
    common_index: dict[str, list[str]],
) -> Classified:
    """변형 한 건을 왕복 + FP로 분류한다."""
    vkey = normalized_key(variant)

    rt_ok, rt_reason = _roundtrip_ok(kind, vkey, surface_key)
    if not rt_ok:
        return Classified(
            surface, term_id, variant, kind, vkey,
            context_required=False, decision="reject", reason=rt_reason,
        )

    collide = common_index.get(vkey)
    fp_safe = not collide

    # chosung: 초성 길이로 단독 매칭 위험 분기 (FP-safe라도 2자는 reject).
    if kind == "chosung":
        clen = len(variant)
        if clen < CHOSUNG_MIN_LEN:
            return Classified(
                surface, term_id, variant, kind, vkey,
                context_required=False, decision="reject",
                reason=f"초성 {clen}자(<{CHOSUNG_MIN_LEN}) — 일반어 충돌 위험(v1 80.2%)",
            )
        if not fp_safe:
            return Classified(
                surface, term_id, variant, kind, vkey,
                context_required=False, decision="reject",
                reason=f"FP 충돌(일반어: {', '.join(collide)})",
            )
        return Classified(
            surface, term_id, variant, kind, vkey,
            context_required=True, decision="verified",
            reason=f"초성 {clen}자 + FP-safe — 단독 매칭 위험 잔존(context_required)",
        )

    # jamo / leet: 왕복OK + FP-safe → verified.
    if not fp_safe:
        return Classified(
            surface, term_id, variant, kind, vkey,
            context_required=False, decision="reject",
            reason=f"FP 충돌(일반어: {', '.join(collide)})",
        )
    return Classified(
        surface, term_id, variant, kind, vkey,
        context_required=False, decision="verified",
        reason="왕복OK + FP-safe",
    )


def classify_terms(terms: list[dict[str, Any]]) -> list[Classified]:
    """용어 목록 전체를 분류한다(결정적 순서: 입력 용어 순 × 변형 생성 순)."""
    common_index = _common_key_index()
    out: list[Classified] = []
    for t in terms:
        surface = t["surface"]
        term_id = int(t["term_id"])
        surface_key = normalized_key(surface)
        for v in generate_variants(surface):
            out.append(
                _classify_variant(
                    surface, term_id, v.variant, v.kind, surface_key, common_index
                )
            )
    return out


# ---------------------------------------------------------------------------
# 리포트
# ---------------------------------------------------------------------------
@dataclass
class _Stats:
    """집계용 카운터."""

    kind_total: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    kind_verified: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    kind_reject: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    kind_collide: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    chosung_len_total: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    chosung_len_verified: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    chosung_len_collide: dict[int, int] = field(default_factory=lambda: defaultdict(int))


def _collect_stats(rows: list[Classified], common_index: dict[str, list[str]]) -> _Stats:
    st = _Stats()
    for r in rows:
        st.kind_total[r.variant_kind] += 1
        if r.decision == "verified":
            st.kind_verified[r.variant_kind] += 1
        else:
            st.kind_reject[r.variant_kind] += 1
        if r.normalized_key in common_index:
            st.kind_collide[r.variant_kind] += 1
        if r.variant_kind == "chosung":
            clen = len(r.variant)
            st.chosung_len_total[clen] += 1
            if r.decision == "verified":
                st.chosung_len_verified[clen] += 1
            if r.normalized_key in common_index:
                st.chosung_len_collide[clen] += 1
    return st


def _pct(num: int, den: int) -> str:
    return f"{(100.0 * num / den):.1f}%" if den else "—"


def _render_report(terms: list[dict[str, Any]], rows: list[Classified]) -> str:
    common_index = _common_key_index()
    st = _collect_stats(rows, common_index)

    verified = [r for r in rows if r.decision == "verified"]
    rejected = [r for r in rows if r.decision == "reject"]

    lines: list[str] = []
    a = lines.append
    a("# 변형 규칙 FP 시뮬레이션 — v2 (verified 분류)")
    a("")
    a("> 생성: `scripts/build_verified_variants.py` (재현 가능, 결정적).")
    a(f"> 대상 active 용어 {len(terms)}개 × `variants.generate_variants`.")
    a(f"> 일반어 코퍼스: `variant_fp_sim.COMMON_WORDS` {len(COMMON_WORDS)}개(재사용).")
    a("")
    a("## 1. 게이트")
    a("")
    a("변형 적재 게이트는 출처가 아니라 **결정성 + 오탐(FP)**이다. 자동 생성 변형은")
    a("결정적 변환이라 날조 리스크가 없고, 유일한 위험은 변형의 normalized_key가")
    a("일반어 키와 충돌해 무해 문장을 오탐하는 것이다.")
    a("")
    a("- 왕복(매칭 가능): jamo는 surface 키로 수렴, leet/chosung은 자기 키로 행 매칭.")
    a(f"- chosung 단독 매칭 안전 하한: 초성 {CHOSUNG_MIN_LEN}자↑(v1 결론: 2자 키 80.2% 충돌).")
    a("")
    a("## 2. 종류별 분류 결과")
    a("")
    a("| kind | 생성 | verified | reject | FP 충돌 | 충돌률 |")
    a("|------|-----:|---------:|-------:|--------:|------:|")
    for kind in ("jamo", "chosung", "leet"):
        t = st.kind_total.get(kind, 0)
        ver = st.kind_verified.get(kind, 0)
        rej = st.kind_reject.get(kind, 0)
        col = st.kind_collide.get(kind, 0)
        a(f"| {kind} | {t} | {ver} | {rej} | {col} | {_pct(col, t)} |")
    a(f"| **합계** | **{len(rows)}** | **{len(verified)}** | **{len(rejected)}** | "
      f"**{sum(st.kind_collide.values())}** | "
      f"**{_pct(sum(st.kind_collide.values()), len(rows))}** |")
    a("")
    a("## 3. chosung 초성 길이별 (단독 매칭 위험 근거)")
    a("")
    a("| 초성 길이 | chosung 수 | verified | FP 충돌 | 충돌률 |")
    a("|----------:|-----------:|---------:|--------:|------:|")
    for clen in sorted(st.chosung_len_total):
        t = st.chosung_len_total[clen]
        ver = st.chosung_len_verified.get(clen, 0)
        col = st.chosung_len_collide.get(clen, 0)
        a(f"| {clen}자 | {t} | {ver} | {col} | {_pct(col, t)} |")
    a("")
    a("- 초성 ≤2자 chosung은 길이 게이트로 **전부 reject**(FP-safe 여부 무관).")
    a(f"- 초성 ≥{CHOSUNG_MIN_LEN}자 chosung은 FP-safe면 verified + `context_required=true`")
    a("  (정규화/매칭 단계에서 단독 매칭 금지 — 엔진 chosung 캡으로 review 상한).")
    a("")
    a("## 4. reject 목록")
    a("")
    if not rejected:
        a("_reject 없음._")
    else:
        a("| surface | 변형 | kind | 키 | 사유 |")
        a("|---------|------|------|----|------|")
        for r in rejected:
            a(f"| `{r.surface}` | `{r.variant}` | {r.variant_kind} | "
              f"`{r.normalized_key}` | {r.reason} |")
    a("")
    a("## 5. verified 카운트 (적재 권고)")
    a("")
    a(f"- verified 합계: **{len(verified)}** "
      f"(jamo {st.kind_verified.get('jamo', 0)}, "
      f"leet {st.kind_verified.get('leet', 0)}, "
      f"chosung {st.kind_verified.get('chosung', 0)}).")
    a(f"- reject 합계: **{len(rejected)}**.")
    a("- chosung verified는 모두 `context_required=true` — 정본 골든셋·엔진 캡과 정합.")
    a("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 입력 용어 (임무 명세에 박힌 active 44 — DB 비접근, 결정적 재현)
# ---------------------------------------------------------------------------
def _active_terms() -> list[dict[str, Any]]:
    """분류 대상 active 용어(surface, term_id). 운영 DB를 읽지 않고 명세값을 쓴다."""
    raw = (REPO_ROOT / "data" / "variants" / "active-terms.json").read_text(encoding="utf-8")
    return json.loads(raw)


def run() -> list[Classified]:
    """분류 + 산출물 기록. 분류 행 리스트를 반환한다."""
    terms = _active_terms()
    rows = classify_terms(terms)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            [
                {
                    "surface": r.surface,
                    "term_id": r.term_id,
                    "variant": r.variant,
                    "variant_kind": r.variant_kind,
                    "normalized_key": r.normalized_key,
                    "context_required": r.context_required,
                    "decision": r.decision,
                    "reason": r.reason,
                }
                for r in rows
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(_render_report(terms, rows), encoding="utf-8")
    return rows


def main() -> int:
    rows = run()
    verified = sum(1 for r in rows if r.decision == "verified")
    rejected = sum(1 for r in rows if r.decision == "reject")
    print(f"[분류] 총 {len(rows)}건 — verified {verified} / reject {rejected}")
    print(f"[저장] {OUTPUT_PATH}")
    print(f"[저장] {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
