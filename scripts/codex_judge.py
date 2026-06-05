"""codex 저지 검수 러너 — candidate_queue의 pending 후보를 codex CLI 판정으로 승인/반려.

2인 원칙(생성자≠승인자, docs/04 §4-4): 후보는 Claude 리서치 에이전트가 생성했으므로
codex가 독립 승인자 역할. 판정 규칙:
  - approve  → console_core.approve_candidate (term은 in_review로 생성 — active 전환은
               라이선스 게이트 프리뷰 + DB 트리거가 최종 방어)
  - reject   → console_core.reject_candidate (사유 기록)
  - uncertain → pending 유지 (사람 검수로 이월)

codex는 자체 샌드박스(bwrap) 불능 환경이므로 --dangerously-bypass-approvals-and-sandbox
로 실행하되, 프롬프트에서 도구 실행 없이 인라인 payload 텍스트만으로 판정하게 한다.

사용:
  DATABASE_URL=postgresql+psycopg://noise:noise@localhost:5455/noise_checker \
    uv run python scripts/codex_judge.py [--ids 1,2] [--limit N] [--dry-run] [--workers 4]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from noise_checker.console_core import (  # noqa: E402
    CHECKLIST_ITEMS,
    approve_candidate,
    reject_candidate,
)

VERDICT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "reject", "uncertain"]},
        "confidence": {"type": "number"},
        "reasons": {"type": "string"},
        "checklist": {
            "type": "object",
            "properties": {item: {"type": "boolean"} for item in CHECKLIST_ITEMS},
            "required": list(CHECKLIST_ITEMS),
            "additionalProperties": False,
        },
        "severity_opinion": {"type": ["integer", "null"]},
        "ambiguity_opinion": {"type": ["string", "null"]},
        "flags": {"type": "array", "items": {"type": "string"}},
    },
    # codex(OpenAI) structured output은 모든 property가 required에 있어야 함
    "required": [
        "verdict", "confidence", "reasons", "checklist",
        "severity_opinion", "ambiguity_opinion", "flags",
    ],
    "additionalProperties": False,
}

PROMPT_TEMPLATE = """\
너는 한국어 혐오표현 사전 구축 프로젝트의 독립 검수자(저지)다. 아래 후보 1건을
판정하라. 도구/명령 실행 없이 이 프롬프트 안의 정보만으로 텍스트 판정만 출력한다.

[판정 기준 — docs/04 §4 검수 체크리스트]
① origin_source: origin/definition evidence ≥ 1, 청정 출처(뉴스/위키백과/페미위키/
   리브레위키/학술/정부). 나무위키·커뮤니티 직접 출처는 부적격.
② homonym_review: 동음이의어 가능성이 검토되었고, 있다면 ambiguity 표시 +
   safe_contexts가 채워져 있는가 (예: '운지'→운지버섯, '한남'→한남동).
③ severity_basis: severity(1~5) 산정이 evidence·실사고 맥락과 정합하는가.
④ category: 카테고리 배정이 적절한가.
⑤ legal_flag: 특정인 실명 비방·기업 실명 incident의 노출 여부가 적절히
   플래그되어 있는가 (incident의 disclosable은 법무 검토 전 false가 기본).

[판정 규칙 — 보수적으로]
- evidence URL이 주장(유래·의미)을 실제로 뒷받침하는지 payload 내 설명으로 판단.
  유래 서술이 출처 없이 단정적이거나 날조 의심이면 reject 또는 uncertain.
  (선례: '보이루'는 법원이 유래 주장 논문 각주를 허위로 판단 → 등재 거부)
- severity나 category가 약간 어긋나는 정도면 approve + flags에 기록.
  구조적 결함(evidence 0, 출처 부적격, 날조 의심)은 reject.
- 확신이 서지 않으면 uncertain (pending 유지되어 사람이 본다).
- checklist의 각 항목은 '이 payload가 그 기준을 충족한다'고 확인한 경우에만 true.

[kind별 적용 범위]
- incident: payload 구조상 ②동음이의어/③severity/④카테고리 필드가 없다(이는 term
  속성). 이 세 항목은 true로 두고 ①출처 적격성과 ⑤법무만 실질 평가하라. incident는
  내부 기록용이며 disclosable=false 기본으로 저장된다 — 실명·기업명이 payload에 있다는
  사실 자체는 reject 사유가 아니다. 청정 출처가 사건을 실제로 뒷받침하면 approve.
- new_marker: ②동음이의어는 '시각적 유사물 오인 가능성(우연한 유사 도형)'으로 해석.

[후보 #{cid} — kind={kind}]
{payload}

마지막 메시지로 JSON만 출력하라 (스키마 강제됨).
"""


def fetch_pending(engine, ids: list[int] | None, limit: int | None):
    from sqlalchemy import text

    sql = "SELECT id, kind, payload FROM candidate_queue WHERE status='pending'"
    if ids:
        sql += " AND id = ANY(:ids)"
    sql += " ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with engine.connect() as conn:
        return [
            (r[0], r[1], r[2])
            for r in conn.execute(text(sql), {"ids": ids} if ids else {})
        ]


def judge_one(cid: int, kind: str, payload: dict, schema_path: str, timeout: int = 420) -> dict:
    """codex exec 1회 호출 → 검증된 verdict dict (실패 시 uncertain)."""
    prompt = PROMPT_TEMPLATE.format(
        cid=cid, kind=kind, payload=json.dumps(payload, ensure_ascii=False, indent=2)
    )
    with tempfile.NamedTemporaryFile(mode="r", suffix=".json", delete=False) as out:
        out_path = out.name
    try:
        proc = subprocess.run(
            [
                "codex", "exec",
                "--dangerously-bypass-approvals-and-sandbox",
                "--skip-git-repo-check",
                "-C", tempfile.gettempdir(),
                "--output-schema", schema_path,
                "-o", out_path,
                "-",
            ],
            input=prompt.encode(),
            capture_output=True,
            timeout=timeout,
        )
        raw = Path(out_path).read_text().strip()
        if not raw:  # -o 파일이 비면 stdout에서 마지막 JSON 블록 추출
            m = re.findall(r"\{.*\}", proc.stdout.decode(), re.DOTALL)
            raw = m[-1] if m else ""
        verdict = json.loads(raw)
        if verdict.get("verdict") not in ("approve", "reject", "uncertain"):
            raise ValueError(f"unexpected verdict: {verdict.get('verdict')}")
        return verdict
    except Exception as exc:  # 파싱/타임아웃/비정상 종료 → 보수적으로 uncertain
        return {
            "verdict": "uncertain",
            "confidence": 0.0,
            "reasons": f"codex 호출/파싱 실패: {exc}",
            "checklist": {item: False for item in CHECKLIST_ITEMS},
            "flags": ["judge_error"],
        }
    finally:
        Path(out_path).unlink(missing_ok=True)


def surface_of(payload: dict) -> str:
    return (
        payload.get("surface")
        or payload.get("marker_name")
        or payload.get("title")
        or payload.get("related_surface")
        or "?"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", help="쉼표 구분 candidate id 목록 (기본: 전체 pending)")
    parser.add_argument("--limit", type=int, help="최대 처리 건수")
    parser.add_argument("--workers", type=int, default=4, help="codex 동시 호출 수")
    parser.add_argument("--dry-run", action="store_true", help="판정만 하고 DB 미반영")
    args = parser.parse_args(argv)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL 미설정", file=sys.stderr)
        return 1

    from sqlalchemy import create_engine

    engine = create_engine(database_url)
    ids = [int(x) for x in args.ids.split(",")] if args.ids else None
    rows = fetch_pending(engine, ids, args.limit)
    if not rows:
        print("pending 후보 없음")
        return 0
    print(f"판정 대상 {len(rows)}건 (workers={args.workers}, dry_run={args.dry_run})")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as schema_file:
        json.dump(VERDICT_SCHEMA, schema_file)
        schema_path = schema_file.name

    # 1) codex 판정 병렬 수집 (DB 쓰기는 이후 순차)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        verdicts = list(
            pool.map(lambda r: judge_one(r[0], r[1], r[2], schema_path), rows)
        )
    Path(schema_path).unlink(missing_ok=True)

    # 2) 순차 반영 — 후보별 독립 트랜잭션 (한 건 실패가 나머지를 막지 않게).
    # incident는 related_surface가 가리키는 term/marker가 먼저 존재해야 하므로
    # kind 우선순위(new_term → new_marker → incident)로 적용 순서를 정렬.
    kind_order = {"new_term": 0, "new_marker": 1, "new_variant": 2, "incident": 3}
    ordered = sorted(
        zip(rows, verdicts, strict=True),
        key=lambda rv: (kind_order.get(rv[0][1], 9), rv[0][0]),
    )
    results = []
    for (cid, kind, payload), v in ordered:
        surface = surface_of(payload)
        applied = "pending(유지)"
        if not args.dry_run and v["verdict"] == "approve":
            try:
                with engine.begin() as conn:
                    approve_candidate(conn, cid, "codex-judge", v["checklist"])
                applied = "approved"
            except Exception as exc:
                v["flags"].append(f"approve 실패→pending: {exc}")
        elif not args.dry_run and v["verdict"] == "reject":
            try:
                with engine.begin() as conn:
                    reject_candidate(conn, cid, "codex-judge", v["reasons"][:500])
                applied = "rejected"
            except Exception as exc:
                v["flags"].append(f"reject 실패→pending: {exc}")
        results.append((cid, kind, surface, v, applied))
        print(f"  #{cid} {kind} {surface}: {v['verdict']} ({v['confidence']:.2f}) → {applied}")

    # 3) 리포트
    today = dt.date.today().isoformat()
    report = Path(__file__).resolve().parents[1] / "reports" / f"codex-judge-{today}.md"
    lines = [
        f"# codex 저지 검수 — {today}",
        "",
        f"대상 {len(results)}건 / approve {sum(1 for r in results if r[4]=='approved')}"
        f" / reject {sum(1 for r in results if r[4]=='rejected')}"
        f" / pending 유지 {sum(1 for r in results if r[4].startswith('pending'))}"
        + (" (dry-run — DB 미반영)" if args.dry_run else ""),
        "",
        "| id | kind | surface | verdict | conf | 적용 | 사유/플래그 |",
        "|---|---|---|---|---|---|---|",
    ]
    for cid, kind, surface, v, applied in results:
        note = v["reasons"].replace("\n", " ")[:200]
        if v.get("flags"):
            note += " ⚑" + "; ".join(v["flags"])[:150]
        lines.append(
            f"| {cid} | {kind} | {surface} | {v['verdict']} | {v['confidence']:.2f}"
            f" | {applied} | {note} |"
        )
    if report.exists():  # 같은 날 재실행 시 이어붙임
        lines = [report.read_text(), "", "## 재실행", ""] + lines[3:]
    report.write_text("\n".join(lines) + "\n")
    print(f"리포트: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
