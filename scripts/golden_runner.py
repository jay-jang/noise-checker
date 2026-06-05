"""골든셋 3종 채점 러너 (M2-C).

noise_checker.engine.Engine(엔진 계약, M2-B 산출)이 import 가능하면 아티팩트
경로를 받아 must_catch / must_pass / evasion 3종을 채점한다. 엔진이 아직 없으면
(M2-B와 병렬 개발 중 — import 실패가 정상) 안내 후 종료한다.

채점 규칙 (docs/06 §1, docs/03 §2 단계4 등급 어휘):
  must_catch  재현율: expected surface 전부가 매칭에 등장하면 통과.
              severity 5 항목은 100% 통과가 게이트(별도 보고).
  must_pass   등급별:
                grade=ambiguous → usage_recommendation=='revise_recommended'
                                  매칭이 하나라도 있으면 실패(review/monitor 통과).
                grade=strict|marketing → 어떤 매칭이든 있으면 실패.
              슬롯별 통과율 분해 + review_recommended 발생률 분리 보고(M3 이후 게이트).
  evasion     재현율: expected surface 전부가 매칭에 등장하면 통과(임계 85%, 점진 상향).

사용:
  python scripts/golden_runner.py <artifact_dir>
  python scripts/golden_runner.py <artifact_dir> --json   # 기계 판독 출력

엔진 계약(noise_checker.engine):
  Engine.load(artifact_dir) -> Engine
  engine.check(text) -> { "overall_recommendation",
                          "matches": [{"surface", "usage_recommendation", ...}] }
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "tests" / "golden"
REVISE = "revise_recommended"


def _load_set(name: str) -> list[dict]:
    path = GOLDEN_DIR / f"{name}.jsonl"
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _matched_surfaces(result: dict) -> set[str]:
    """엔진 응답에서 매칭된 surface 집합."""
    return {m.get("surface") for m in result.get("matches", [])}


def _has_revise(result: dict) -> bool:
    return any(
        m.get("usage_recommendation") == REVISE for m in result.get("matches", [])
    )


def _has_any_match(result: dict) -> bool:
    return bool(result.get("matches"))


def _has_review(result: dict) -> bool:
    return any(
        m.get("usage_recommendation") == "review_recommended"
        for m in result.get("matches", [])
    )


# ── 채점기 ──────────────────────────────────────────────────────────────────

def score_must_catch(engine) -> dict:
    entries = _load_set("must_catch")
    passed = 0
    sev5_total = sev5_passed = 0
    failures = []
    for e in entries:
        result = engine.check(e["text"])
        got = _matched_surfaces(result)
        ok = all(surf in got for surf in e["expected"])
        is_sev5 = e.get("severity") == 5
        if is_sev5:
            sev5_total += 1
            sev5_passed += int(ok)
        if ok:
            passed += 1
        else:
            failures.append(
                {"text": e["text"], "expected": e["expected"], "got": sorted(got)}
            )
    total = len(entries)
    return {
        "total": total,
        "passed": passed,
        "recall": passed / total if total else 1.0,
        "sev5_total": sev5_total,
        "sev5_passed": sev5_passed,
        "sev5_recall": sev5_passed / sev5_total if sev5_total else 1.0,
        "failures": failures,
    }


def score_must_pass(engine) -> dict:
    entries = _load_set("must_pass")
    passed = 0
    by_slot_total: dict[str, int] = defaultdict(int)
    by_slot_passed: dict[str, int] = defaultdict(int)
    review_hits = 0  # ambiguous에서 review_recommended 발생(분리 보고, M3 이후 게이트)
    failures = []
    for e in entries:
        result = engine.check(e["text"])
        grade = e.get("grade", "strict")
        slot = e.get("slot", "?")
        if grade == "ambiguous":
            failed = _has_revise(result)
            if _has_review(result):
                review_hits += 1
        else:  # strict | marketing
            failed = _has_any_match(result)
        ok = not failed
        by_slot_total[slot] += 1
        by_slot_passed[slot] += int(ok)
        if ok:
            passed += 1
        else:
            failures.append(
                {
                    "text": e["text"],
                    "slot": slot,
                    "grade": grade,
                    "overall": result.get("overall_recommendation"),
                    "matches": sorted(_matched_surfaces(result)),
                }
            )
    total = len(entries)
    slot_pass_rate = {
        s: by_slot_passed[s] / by_slot_total[s] for s in sorted(by_slot_total)
    }
    return {
        "total": total,
        "passed": passed,
        "pass_rate": passed / total if total else 1.0,
        "slot_pass_rate": slot_pass_rate,
        "review_hits_ambiguous": review_hits,
        "failures": failures,
    }


def score_evasion(engine) -> dict:
    entries = _load_set("evasion")
    passed = 0
    by_kind_total: dict[str, int] = defaultdict(int)
    by_kind_passed: dict[str, int] = defaultdict(int)
    failures = []
    for e in entries:
        result = engine.check(e["text"])
        got = _matched_surfaces(result)
        ok = all(surf in got for surf in e["expected"])
        kind = e.get("evasion_kind", "?")
        by_kind_total[kind] += 1
        by_kind_passed[kind] += int(ok)
        if ok:
            passed += 1
        else:
            failures.append(
                {
                    "text": e["text"],
                    "expected": e["expected"],
                    "kind": kind,
                    "rely_on": e.get("rely_on"),
                    "got": sorted(got),
                }
            )
    total = len(entries)
    kind_recall = {
        k: by_kind_passed[k] / by_kind_total[k] for k in sorted(by_kind_total)
    }
    return {
        "total": total,
        "passed": passed,
        "recall": passed / total if total else 1.0,
        "kind_recall": kind_recall,
        "failures": failures,
    }


# ── 게이트 판정 (06 §1 합격 기준) ──────────────────────────────────────────

def evaluate_gates(mc: dict, mp: dict, ev: dict) -> dict:
    return {
        "must_catch_recall>=0.95": mc["recall"] >= 0.95,
        "must_catch_sev5==1.0": mc["sev5_recall"] >= 1.0,
        "must_pass_rate>=0.98": mp["pass_rate"] >= 0.98,
        "evasion_recall>=0.85": ev["recall"] >= 0.85,
    }


def _print_report(mc: dict, mp: dict, ev: dict, gates: dict) -> None:
    print("=" * 64)
    print("골든셋 3종 채점 리포트")
    print("=" * 64)
    print(
        f"[must_catch] 재현율 {mc['recall']:.1%} "
        f"({mc['passed']}/{mc['total']})  |  "
        f"severity5 재현율 {mc['sev5_recall']:.1%} "
        f"({mc['sev5_passed']}/{mc['sev5_total']})"
    )
    for f in mc["failures"]:
        print(f"   MISS: {f['text']!r} expected={f['expected']} got={f['got']}")

    print(
        f"[must_pass] 통과율 {mp['pass_rate']:.1%} "
        f"({mp['passed']}/{mp['total']})  |  "
        f"ambiguous review 발생 {mp['review_hits_ambiguous']}건(분리 보고)"
    )
    for slot, rate in mp["slot_pass_rate"].items():
        print(f"   슬롯 {slot:14s} 통과율 {rate:.1%}")
    for f in mp["failures"]:
        print(
            f"   FP: {f['text']!r} slot={f['slot']} grade={f['grade']} "
            f"matches={f['matches']} overall={f['overall']}"
        )

    print(f"[evasion] 재현율 {ev['recall']:.1%} ({ev['passed']}/{ev['total']})")
    for kind, rate in ev["kind_recall"].items():
        print(f"   변형종류 {kind:24s} 재현율 {rate:.1%}")
    for f in ev["failures"]:
        print(
            f"   ESCAPE: {f['text']!r} kind={f['kind']} "
            f"rely_on={f['rely_on']} got={f['got']}"
        )

    print("-" * 64)
    print("게이트:")
    for name, ok in gates.items():
        print(f"   [{'PASS' if ok else 'FAIL'}] {name}")
    print("=" * 64)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="골든셋 3종 채점 러너")
    parser.add_argument("artifact_dir", nargs="?", help="릴리스 아티팩트 디렉토리")
    parser.add_argument("--json", action="store_true", help="기계 판독 JSON 출력")
    args = parser.parse_args(argv)

    try:
        from noise_checker.engine import Engine  # noqa: PLC0415
    except ImportError:
        print(
            "noise_checker.engine 미존재 — M2-B(엔진) 병렬 개발 중이므로 정상입니다.\n"
            "엔진이 머지되면 다음으로 채점하세요:\n"
            "  python scripts/golden_runner.py <artifact_dir>\n"
            "골든셋 자산 자체의 정합성은 `uv run pytest tests/test_golden_schema.py`로 검증됩니다.",
            file=sys.stderr,
        )
        return 0

    if not args.artifact_dir:
        parser.error("엔진이 존재합니다 — artifact_dir 인자가 필요합니다.")

    engine = Engine.load(args.artifact_dir)
    mc = score_must_catch(engine)
    mp = score_must_pass(engine)
    ev = score_evasion(engine)
    gates = evaluate_gates(mc, mp, ev)

    if args.json:
        print(json.dumps(
            {"must_catch": mc, "must_pass": mp, "evasion": ev, "gates": gates},
            ensure_ascii=False, indent=2,
        ))
    else:
        _print_report(mc, mp, ev, gates)

    return 0 if all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
