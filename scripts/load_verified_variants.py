"""verified 변형을 term_variant에 적재 (auto_generated=true·verified=true).

적재 정책 (2026-06-08 — 적대적 검증 + 광역 FP 재확인 반영):
  - leet 전량: 키에 비한글 문자(숫자/라틴) 보유 → 365k 사전과 구조적 0 충돌.
  - chosung 4자만: 3자는 흔한 무해 chosung 채팅과 충돌(ㄱㅊㄴ=괜찮네 등). 4자도
    광역 사전으로 재확인해 충돌분(결정장애 ㄱㅈㅈㅇ=경제정의/거주지역) 제외.
  - jamo 제외: normalizer 수렴으로 surface 키와 동일 — 중복(무의미).

mechanical 변형은 출처가 아니라 FP 시뮬이 검증 게이트이므로 candidate_queue를
거치지 않고 직접 적재한다(02 §3.4 auto_generated 경로). 부모 term은 surface로 해석.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from noise_checker.normalizer import normalized_key  # noqa: E402

MANIFEST = Path(__file__).resolve().parents[1] / "data/variants/verified-2026-06-08.json"
# 광역 FP 재확인으로 제외된 4자 chosung(검증자 미검토분 중 충돌 발견).
_EXCLUDE_CHOSUNG = frozenset({"ㄱㅈㅈㅇ"})  # 결정장애 = 경제정의/거주지역
REVIEWER = "auto:variant-fp-verified-2026-06-08"


def _is_fp_safe_leet(nkey: str) -> bool:
    """leet 키는 비한글 문자(숫자/라틴)를 1자 이상 가져야 구조적 FP-safe."""
    return any(not ("가" <= c <= "힣" or "ㄱ" <= c <= "ㅣ") for c in nkey)


def select_variants() -> list[dict]:
    items = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = []
    for it in items:
        if it.get("decision") != "verified":
            continue
        kind, var, nkey = it["variant_kind"], it["variant"], it["normalized_key"]
        # leet: 비한글 문자 보유로 구조적 FP-safe / chosung: 4자만(3자 제외).
        # jamo는 normalizer 수렴으로 surface 키와 동일 — 중복이라 제외.
        if (kind == "leet" and _is_fp_safe_leet(nkey)) or (
            kind == "chosung" and len(var) == 4 and var not in _EXCLUDE_CHOSUNG
        ):
            out.append(it)
    return out


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL 미설정", file=sys.stderr)
        return 1
    from sqlalchemy import create_engine, text

    selected = select_variants()
    from collections import Counter

    by_kind = Counter(s["variant_kind"] for s in selected)
    print(f"적재 대상 {len(selected)}건: {dict(by_kind)}")

    eng = create_engine(database_url)
    loaded = skipped = noparent = 0
    with eng.begin() as conn:
        for s in selected:
            tid = conn.execute(
                text(
                    "SELECT id FROM term WHERE normalized_key=:nk AND status='active' "
                    "ORDER BY id LIMIT 1"
                ),
                {"nk": normalized_key(s["surface"])},
            ).fetchone()
            if tid is None:
                print(f"  부모 미해결(스킵): {s['surface']} {s['variant']}")
                noparent += 1
                continue
            tid = tid[0]
            row = conn.execute(
                text(
                    "INSERT INTO term_variant (term_id, variant, variant_kind, "
                    "normalized_key, auto_generated, verified) "
                    "VALUES (:t, :v, :k, :nk, true, true) "
                    "ON CONFLICT (term_id, variant) DO NOTHING RETURNING id"
                ),
                {"t": tid, "v": s["variant"], "k": s["variant_kind"], "nk": s["normalized_key"]},
            ).fetchone()
            if row is None:
                skipped += 1
            else:
                loaded += 1
        conn.execute(
            text(
                "INSERT INTO review_log (entity_type, entity_id, action, reviewer, rationale) "
                "VALUES ('term', 0, 'variants_loaded', :r, :msg)"
            ),
            {
                "r": REVIEWER,
                "msg": f"verified 변형 {loaded}건 적재(leet+4자chosung, FP재확인). "
                f"skip {skipped}/noparent {noparent}",
            },
        )
    print(f"적재 {loaded} / 중복 skip {skipped} / 부모 미해결 {noparent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
