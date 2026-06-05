"""릴리스 빌더 v1 (M2-A).

docs/03-architecture.md §1(빌드계), §7(핫리로드·normalizer_code_version),
docs/02-database-design.md §3.10(dictionary_release·아티팩트 구성), §5(배포 정책)을 구현한다.

DB의 `status IN ('active','watchlist')` term과 verified 변형·safe_contexts·카테고리·
조합 규칙을 읽어 검사 엔진이 로드하는 **릴리스 아티팩트 디렉토리**를 생성한다.
검사 API는 DB를 직접 읽지 않고 이 아티팩트만 로드한다(02 §3.10).

아티팩트 계약 v1 (manifest.json / terms.json / kiwi_user_dict.tsv):
  - normalized_key는 반드시 noise_checker.normalizer.normalize()로 **재생성**한다
    (DB 저장값을 신뢰하지 않음 — 빌드 시점 normalizer 코드가 단일 진실).
  - manifest.normalizer_code_version = normalizer.NORMALIZER_VERSION (엔진이 로드 시 대조).
  - release_policy in (internal_only, hold_legal)는 고객 노출 아티팩트에서 제외(02 §5).
    라이선스 게이트는 DB 트리거가 active 전환을 이미 막으므로 빌더는 status 기준으로만 판정.

CLI: python -m noise_checker.release_builder --out dist/releases/ [--version YYYY.MM.DD-N]
     (DATABASE_URL 환경변수 사용)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from noise_checker.normalizer import NORMALIZER_VERSION, normalize

__all__ = ["build_release", "next_version"]

# 고객 노출 아티팩트에서 제외하는 배포 정책 (02 §5: internal_only=내부 전용, hold_legal=법무 보류).
_EXCLUDED_RELEASE_POLICIES = ("internal_only", "hold_legal")

# kiwi 사용자 사전 품사·가중치 (NNP 고유명사로 등록해 형태소 오분해 방지, 04 §5).
_KIWI_TAG = "NNP"
_KIWI_SCORE = "-1.0"

# kiwi 사전에 넣지 않을 변형 종류 — 자모분리(jamo)·초성(chosung)은 형태소가 아니므로
# Kiwi 사용자 사전에 부적합(임무 명세). surface와 음절형 변형(leet/translit/spacing 등)만 등록.
_KIWI_EXCLUDED_VARIANT_KINDS = frozenset({"jamo", "chosung"})

_VERSION_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})-(\d+)$")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def next_version(out_dir: Path, *, today: str | None = None) -> str:
    """YYYY.MM.DD-N 버전 생성. out_dir의 같은 날짜 디렉토리를 스캔해 N을 증가시킨다.

    today: 'YYYY.MM.DD' (테스트 주입용). 미지정 시 UTC 오늘 날짜.
    """
    if today is None:
        today = datetime.now(UTC).strftime("%Y.%m.%d")

    max_n = 0
    if out_dir.is_dir():
        for child in out_dir.iterdir():
            if not child.is_dir():
                continue
            m = _VERSION_RE.match(child.name)
            if m is None:
                continue
            if f"{m.group(1)}.{m.group(2)}.{m.group(3)}" == today:
                max_n = max(max_n, int(m.group(4)))
    return f"{today}-{max_n + 1}"


def _fetch_terms(conn) -> list[dict[str, Any]]:
    """status IN ('active','watchlist')이고 배포 가능한 term + 부속 데이터를 읽는다."""
    from sqlalchemy import text

    rows = conn.execute(
        text(
            "SELECT id, surface, term_kind, severity, ambiguity, status, "
            "release_policy, safe_contexts "
            "FROM term "
            "WHERE status IN ('active','watchlist') "
            "  AND release_policy NOT IN ('internal_only','hold_legal') "
            "ORDER BY id"
        )
    ).fetchall()

    terms: list[dict[str, Any]] = []
    for r in rows:
        term_id = r[0]
        terms.append(
            {
                "term_id": term_id,
                "surface": r[1],
                "term_kind": r[2],
                "severity": int(r[3]),
                "ambiguity": r[4],
                "status": r[5],
                # 도그휘슬·의도성 미입증 표식 = release_policy 'advisory_only'
                # (02 §3.2 / 03 §2 정책표 1행: 상한 review_recommended).
                "is_dogwhistle_marker": r[6] == "advisory_only",
                "safe_contexts": list(r[7]) if r[7] else [],
                "release_policy": r[6],
                "categories": _fetch_categories(conn, term_id),
                "variants": _fetch_variants(conn, term_id),
                "combination_rules": _fetch_combination_rules(conn, term_id),
            }
        )
    return terms


def _fetch_categories(conn, term_id: int) -> list[str]:
    from sqlalchemy import text

    rows = conn.execute(
        text(
            "SELECT c.code FROM term_category tc "
            "JOIN category c ON c.id = tc.category_id "
            "WHERE tc.term_id = :t ORDER BY c.code"
        ),
        {"t": term_id},
    ).fetchall()
    return [r[0] for r in rows]


def _fetch_variants(conn, term_id: int) -> list[dict[str, Any]]:
    """verified 변형만 (미검증 자동생성은 release 제외 — 02 §3.4)."""
    from sqlalchemy import text

    rows = conn.execute(
        text(
            "SELECT variant, variant_kind FROM term_variant "
            "WHERE term_id = :t AND verified = true "
            "ORDER BY id"
        ),
        {"t": term_id},
    ).fetchall()
    return [
        {
            "surface": r[0],
            "normalized_key": normalize(r[0])[0],
            "variant_kind": r[1],
        }
        for r in rows
    ]


def _fetch_combination_rules(conn, term_id: int) -> list[dict[str, Any]]:
    """active 조합 규칙만 (number/common 항목의 composite 조건 — 02 §3.8)."""
    from sqlalchemy import text

    rows = conn.execute(
        text(
            "SELECT trigger_kind, trigger_terms, trigger_pattern, proximity_window, "
            "base_severity, severity_delta "
            "FROM composite_rule "
            "WHERE primary_term_id = :t AND status = 'active' "
            "ORDER BY id"
        ),
        {"t": term_id},
    ).fetchall()
    return [
        {
            "trigger_kind": r[0],
            "trigger_terms": list(r[1]) if r[1] else [],
            "trigger_pattern": r[2],
            "proximity_window": r[3],
            "base_severity": int(r[4]),
            "severity_delta": int(r[5]),
        }
        for r in rows
    ]


def _build_terms_json(terms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """계약 v1 terms.json 항목으로 변환. normalized_key는 normalize()로 재생성."""
    out: list[dict[str, Any]] = []
    for t in terms:
        out.append(
            {
                "term_id": t["term_id"],
                "surface": t["surface"],
                "term_kind": t["term_kind"],
                "normalized_key": normalize(t["surface"])[0],
                "severity": t["severity"],
                "ambiguity": t["ambiguity"],
                "status": t["status"],
                "release_policy": t["release_policy"],
                "categories": t["categories"],
                "safe_contexts": t["safe_contexts"],
                "is_dogwhistle_marker": t["is_dogwhistle_marker"],
                "variants": t["variants"],
                "combination_rules": t["combination_rules"],
            }
        )
    return out


def _build_kiwi_dict(terms: list[dict[str, Any]]) -> str:
    """kiwi_user_dict.tsv 본문 — active surface + verified 음절형 변형(NNP, 탭 구분).

    자모분리/초성형 변형은 형태소가 아니므로 제외(임무 명세). 결정적 순서·중복 제거.
    """
    seen: set[str] = set()
    lines: list[str] = []
    for t in terms:
        # surface는 active만 등록(watchlist는 monitor 고정 — 경계 보강은 active 검사 경로).
        forms: list[str] = []
        if t["status"] == "active":
            forms.append(t["surface"])
            for v in t["variants"]:
                if v["variant_kind"] in _KIWI_EXCLUDED_VARIANT_KINDS:
                    continue
                forms.append(v["surface"])
        for form in forms:
            form = form.strip()
            if not form or form in seen:
                continue
            seen.add(form)
            lines.append(f"{form}\t{_KIWI_TAG}\t{_KIWI_SCORE}")
    return "\n".join(lines) + ("\n" if lines else "")


def build_release(
    database_url: str,
    out_dir: str | Path,
    version: str | None = None,
) -> dict[str, Any]:
    """릴리스 아티팩트 디렉토리를 생성하고 manifest dict를 반환한다.

    out_dir/<version>/ 아래에 terms.json, kiwi_user_dict.tsv, manifest.json을 쓴다.
    """
    import sqlalchemy

    out_dir = Path(out_dir)
    if version is None:
        version = next_version(out_dir)

    engine = sqlalchemy.create_engine(database_url, poolclass=sqlalchemy.pool.NullPool)
    try:
        with engine.connect() as conn:
            terms = _fetch_terms(conn)
    finally:
        engine.dispose()

    terms_json = _build_terms_json(terms)
    kiwi_dict = _build_kiwi_dict(terms)
    variant_count = sum(len(t["variants"]) for t in terms)

    release_dir = out_dir / version
    release_dir.mkdir(parents=True, exist_ok=True)

    terms_path = release_dir / "terms.json"
    kiwi_path = release_dir / "kiwi_user_dict.tsv"
    terms_path.write_text(
        json.dumps(terms_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    kiwi_path.write_text(kiwi_dict, encoding="utf-8")

    manifest = {
        "release_version": version,
        "created_at": datetime.now(UTC).isoformat(),
        "normalizer_code_version": NORMALIZER_VERSION,
        "term_count": len(terms_json),
        "variant_count": variant_count,
        "checksums": {
            "terms.json": _sha256_file(terms_path),
            "kiwi_user_dict.tsv": _sha256_file(kiwi_path),
        },
    }
    (release_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m noise_checker.release_builder",
        description="릴리스 아티팩트 빌더 (DATABASE_URL 환경변수 사용)",
    )
    parser.add_argument(
        "--out", required=True, help="릴리스 출력 루트 디렉토리 (예: dist/releases/)"
    )
    parser.add_argument(
        "--version", default=None, help="버전 강제 (기본: YYYY.MM.DD-N 자동)"
    )
    args = parser.parse_args(argv)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        parser.error("DATABASE_URL 환경변수가 필요합니다.")

    manifest = build_release(database_url, args.out, version=args.version)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
