"""후보 적재 도구 (loader) — payload 파일 → candidate_queue.

docs/04-update-pipeline.md §3 (candidate_queue 스키마·점수화) 구현.
입력 파일(candidate-payload 형식 또는 레거시 candidate-term 단독 형식)을
candidate-payload 스키마로 검증하고 candidate_queue에 멱등 적재한다.

수용 형식:
  1. candidate-payload: {kind, collector, payload}
  2. 레거시 candidate-term 단독: kind/collector 없는 기존 엔트리
     → new_term payload로 자동 래핑 (collector='manual:legacy-file').

적재 규약:
  - dedup_key = f"{kind}:{normalized_key(대표표기)}"
    (new_term/new_variant=surface·variant, new_marker=name,
     incident=title, deprecation=target_surface)
  - UNIQUE(dedup_key, kind) 충돌 시 skip (ON CONFLICT DO NOTHING + 보고)
  - signal_score = evidence 수×1.0 + incident evidence 수×2.0
    + related_incidents 수×2.0 (상한 10.0), urgency='normal' 고정

CLI:
  uv run python -m noise_checker.loader <경로...> [--dry-run]
  --dry-run: DB 접속 없이 검증 + 적재 계획만 출력.

종료코드: 검증 실패가 하나라도 있으면 1, 아니면 0.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

from noise_checker.normalizer import normalized_key

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "data" / "schema"

LEGACY_COLLECTOR = "manual:legacy-file"

# candidate-term 단독 형식(레거시)을 식별하기 위한 필수 필드.
# candidate-term.schema.json required와 일치.
_LEGACY_TERM_REQUIRED = frozenset(
    {"surface", "meaning", "origin_story", "severity", "ambiguity", "categories", "evidence"}
)

SIGNAL_SCORE_CAP = 10.0


def build_validator() -> Draft202012Validator:
    """candidate-payload 스키마 검증기 ($ref는 로컬 레지스트리에서만 해석)."""
    resources = []
    payload_schema = None
    for p in SCHEMA_DIR.glob("*.json"):
        s = json.loads(p.read_text(encoding="utf-8"))
        sid = s.get("$id", p.name)
        resources.append((sid, Resource.from_contents(s)))
        if sid == "noise-checker/candidate-payload":
            payload_schema = s
    if payload_schema is None:
        raise SystemExit("candidate-payload 스키마를 찾지 못함")
    registry = Registry().with_resources(resources)
    return Draft202012Validator(payload_schema, registry=registry)


def _leaf_errors(errors: list[ValidationError]) -> list[ValidationError]:
    """oneOf/allOf 분기로 인해 root에 뭉친 에러를 가장 구체적인 하위 에러까지
    펼친다 (candidate-payload는 kind별 oneOf 분기라 root 에러만으로는
    '어느 필드가 문제인지'가 보이지 않음)."""
    leaves: list[ValidationError] = []
    for e in errors:
        if e.context:
            leaves.extend(_leaf_errors(list(e.context)))
        else:
            leaves.append(e)
    return leaves


def format_errors(errors: list[ValidationError]) -> str:
    leaves = sorted(_leaf_errors(errors), key=lambda e: list(e.absolute_path))
    lines = []
    for e in leaves[:10]:
        loc = "/".join(str(x) for x in e.absolute_path) or "(root)"
        lines.append(f"  - {loc}: {e.message[:200]}")
    return "스키마 위반\n" + "\n".join(lines)


def discover_paths(inputs: list[str]) -> list[Path]:
    """입력(파일/디렉토리)에서 *.json 파일을 재귀 수집 (정렬)."""
    found: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            found.extend(sorted(path.rglob("*.json")))
        else:
            found.append(path)
    return found


def is_legacy_term(doc: dict) -> bool:
    """레거시 candidate-term 단독 형식인지 판정.

    candidate-payload는 top-level에 kind/collector/payload를 가진다.
    레거시는 그것이 없고 candidate-term 필수 필드를 직접 가진다.
    """
    if doc.keys() >= {"kind", "collector", "payload"}:
        return False
    return doc.keys() >= _LEGACY_TERM_REQUIRED


def wrap_legacy(doc: dict) -> dict:
    """레거시 candidate-term 단독 엔트리를 new_term payload로 래핑."""
    payload = {k: v for k, v in doc.items() if not k.startswith("_")}
    return {
        "kind": "new_term",
        "collector": LEGACY_COLLECTOR,
        "payload": payload,
    }


def representative_surface(kind: str, payload: dict) -> str | None:
    """dedup_key 계산에 쓰는 대표 표기 추출 (kind별)."""
    if kind in ("new_term", "deprecation"):
        # new_term=surface, deprecation=target_surface
        return payload.get("surface") if kind == "new_term" else payload.get("target_surface")
    if kind == "new_variant":
        return payload.get("variant")
    if kind == "new_marker":
        return payload.get("name")
    if kind == "incident":
        return payload.get("title")
    return None


def compute_dedup_key(kind: str, payload: dict) -> str:
    surface = representative_surface(kind, payload)
    if surface is None:
        raise ValueError(f"대표 표기를 찾을 수 없음 (kind={kind})")
    return f"{kind}:{normalized_key(surface)}"


def compute_signal_score(payload: dict) -> float:
    """evidence 수×1.0 + incident evidence 수×2.0 + related_incidents 수×2.0 (상한 10.0)."""
    evidence = payload.get("evidence") or []
    incident_evidence = sum(
        1 for e in evidence if isinstance(e, dict) and e.get("evidence_type") == "incident"
    )
    related = payload.get("related_incidents") or []
    score = len(evidence) * 1.0 + incident_evidence * 2.0 + len(related) * 2.0
    return min(score, SIGNAL_SCORE_CAP)


@dataclass
class LoadItem:
    """검증 통과한 적재 후보 한 건."""

    path: Path
    kind: str
    collector: str
    payload: dict
    dedup_key: str
    signal_score: float


@dataclass
class PrepareResult:
    items: list[LoadItem]
    failures: list[tuple[Path, str]]  # (경로, 에러 상세)


def prepare(paths: list[Path], validator: Draft202012Validator) -> PrepareResult:
    """파일을 읽어 (래핑 후) 검증하고 적재 후보를 구성한다. DB 접속 없음."""
    items: list[LoadItem] = []
    failures: list[tuple[Path, str]] = []

    for path in paths:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            failures.append((path, f"파일/JSON 오류 — {e}"))
            continue
        if not isinstance(doc, dict):
            failures.append((path, "최상위가 객체(JSON object)가 아님"))
            continue

        candidate = wrap_legacy(doc) if is_legacy_term(doc) else doc

        errors = list(validator.iter_errors(candidate))
        if errors:
            failures.append((path, format_errors(errors)))
            continue

        kind = candidate["kind"]
        collector = candidate["collector"]
        payload = candidate["payload"]
        try:
            dedup_key = compute_dedup_key(kind, payload)
        except ValueError as e:
            failures.append((path, str(e)))
            continue
        signal_score = compute_signal_score(payload)
        items.append(
            LoadItem(
                path=path,
                kind=kind,
                collector=collector,
                payload=payload,
                dedup_key=dedup_key,
                signal_score=signal_score,
            )
        )

    return PrepareResult(items=items, failures=failures)


def insert_items(items: list[LoadItem], database_url: str) -> tuple[int, int]:
    """candidate_queue에 멱등 적재. (적재 수, 중복 skip 수) 반환.

    ON CONFLICT (dedup_key, kind) DO NOTHING — UNIQUE 충돌 시 skip.
    """
    import psycopg

    dsn = database_url.replace("postgresql+psycopg://", "postgresql://")
    inserted = 0
    skipped = 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(
                    "INSERT INTO candidate_queue "
                    "(payload, kind, collector, signal_score, urgency, dedup_key) "
                    "VALUES (%s, %s, %s, %s, 'normal', %s) "
                    "ON CONFLICT (dedup_key, kind) DO NOTHING "
                    "RETURNING id",
                    (
                        json.dumps(item.payload, ensure_ascii=False),
                        item.kind,
                        item.collector,
                        item.signal_score,
                        item.dedup_key,
                    ),
                )
                if cur.fetchone() is None:
                    skipped += 1
                else:
                    inserted += 1
        conn.commit()
    return inserted, skipped


def run(inputs: list[str], dry_run: bool, database_url: str | None) -> int:
    validator = build_validator()
    paths = discover_paths(inputs)
    if not paths:
        print("입력에서 *.json 파일을 찾지 못함", file=sys.stderr)
        return 1

    result = prepare(paths, validator)

    for path, detail in result.failures:
        print(f"FAIL {path}: {detail}")

    if dry_run:
        print("\n[DRY-RUN] 적재 계획:")
        for item in result.items:
            print(
                f"  PLAN {item.path}: kind={item.kind} "
                f"dedup_key={item.dedup_key!r} signal_score={item.signal_score} "
                f"collector={item.collector}"
            )
        print(
            f"\n요약(dry-run): 적재 예정 {len(result.items)} / "
            f"검증 실패 {len(result.failures)}"
        )
        return 1 if result.failures else 0

    if database_url is None:
        print(
            "DATABASE_URL 미설정 — 적재 불가 (--dry-run 사용 또는 DATABASE_URL 설정)",
            file=sys.stderr,
        )
        return 1

    inserted, skipped = insert_items(result.items, database_url)
    print(
        f"\n요약: 적재 {inserted} / 중복 skip {skipped} / 검증 실패 {len(result.failures)}"
    )
    return 1 if result.failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="noise_checker.loader",
        description="후보 payload 파일을 검증·적재한다 (candidate_queue).",
    )
    parser.add_argument("paths", nargs="+", help="파일 또는 디렉토리(재귀 *.json)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB 접속 없이 검증 + 적재 계획만 출력",
    )
    args = parser.parse_args(argv)
    database_url = os.environ.get("DATABASE_URL")
    return run(args.paths, args.dry_run, database_url)


if __name__ == "__main__":
    sys.exit(main())
