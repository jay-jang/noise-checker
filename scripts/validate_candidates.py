"""후보 파일(candidate-payload 스키마) 검증 CLI.

사용: uv run python scripts/validate_candidates.py data/seed/candidates/*.json
종료코드: 전부 통과 0, 하나라도 실패 1.
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "data" / "schema"


def build_validator() -> Draft202012Validator:
    resources = []
    payload_schema = None
    for p in SCHEMA_DIR.glob("*.json"):
        s = json.loads(p.read_text())
        sid = s.get("$id", p.name)
        resources.append((sid, Resource.from_contents(s)))
        if sid == "noise-checker/candidate-payload":
            payload_schema = s
    if payload_schema is None:
        raise SystemExit("candidate-payload 스키마를 찾지 못함")
    registry = Registry().with_resources(resources)
    return Draft202012Validator(payload_schema, registry=registry)


def main(paths: list[str]) -> int:
    validator = build_validator()
    failed = 0
    for raw in paths:
        path = Path(raw)
        try:
            doc = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            print(f"FAIL {path}: 파일/JSON 오류 — {e}")
            failed += 1
            continue
        errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
        if errors:
            failed += 1
            print(f"FAIL {path}:")
            for e in errors[:10]:
                loc = "/".join(str(x) for x in e.absolute_path) or "(root)"
                print(f"  - {loc}: {e.message[:200]}")
        else:
            print(f"OK   {path}")
    print(f"\n요약: {len(paths) - failed} 통과 / {failed} 실패")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1:]))
