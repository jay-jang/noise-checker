"""골든셋 3종(tests/golden/*.jsonl) 계약 검증.

검증 항목:
  1. 모든 행이 golden-entry.schema.json을 통과한다 (스키마 준수).
  2. set 필드가 파일명과 일치한다.
  3. text 중복이 없다 (셋 내부).
  4. must_pass 슬롯 커버리지 최소치 (HateCheck 슬롯당 ≥5, 큐 19개 용어 전부 F8 ≥1).
  5. must_catch 분량(≥40)·severity 5 정착 용례 포함.
  6. evasion 분량(큐 용어 기준 자연 분량)·정규화 수렴 항목의 수렴 불변식.
  7. must_pass 채점 메타(grade)가 허용값인지.

엔진(noise_checker.engine)에 의존하지 않는다 — 골든셋 자산 자체의 정합성만 본다.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from noise_checker.normalizer import normalize, normalized_key

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "tests" / "golden"
SCHEMA_PATH = ROOT / "data" / "schema" / "golden-entry.schema.json"

# 큐 19개 용어 — 03/05/M2-C 브리프 기준. 각 용어는 must_pass F8(동음이의어)에
# 최소 1개의 무해 용례를 가져야 한다(브리프 요구).
QUEUE_TERMS = [
    "운지", "노무", "노알라", "응디", "삼일한", "한남", "홍어", "된장녀", "김치녀",
    "맘충", "군무새", "전라디언", "좌좀", "오조오억", "허버허버", "웅앵웅", "오또케",
    "슨상님", "503", "~노",
]

# must_pass 채점 grade 허용값 (06 §1 채점 규칙 반영).
#  - ambiguous: ambiguity != unambiguous 슬롯 → revise_recommended만 실패.
#  - strict: unambiguous/safe_contexts 해소형/jamo_boundary/F11 → 어떤 매칭도 실패.
#  - marketing: 무해 마케팅 카피(사전 용어 미포함) → 어떤 매칭도 실패(strict와 동일 채점).
VALID_GRADES = {"ambiguous", "strict", "marketing"}

HATECHECK_SLOTS = {"F8", "F9", "F11", "F18", "F19", "F20", "F21", "jamo_boundary"}


def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _load_set(name: str) -> list[dict]:
    path = GOLDEN_DIR / f"{name}.jsonl"
    entries: list[dict] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as exc:  # pragma: no cover - 방어
            raise AssertionError(f"{name}.jsonl:{lineno} JSON 파싱 실패: {exc}") from exc
    return entries


ALL_SETS = ("must_catch", "must_pass", "evasion")


# ── 1. 스키마 준수 ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("set_name", ALL_SETS)
def test_every_entry_matches_schema(set_name: str):
    validator = _validator()
    for i, entry in enumerate(_load_set(set_name)):
        errors = sorted(validator.iter_errors(entry), key=lambda e: e.path)
        assert not errors, f"{set_name}[{i}] 스키마 위반: {[e.message for e in errors]}"


# ── 2. set 필드 일치 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("set_name", ALL_SETS)
def test_set_field_matches_filename(set_name: str):
    for i, entry in enumerate(_load_set(set_name)):
        assert entry.get("set") == set_name, f"{set_name}[{i}] set 불일치: {entry.get('set')}"


# ── 3. text 중복 없음 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("set_name", ALL_SETS)
def test_no_duplicate_text(set_name: str):
    texts = [e["text"] for e in _load_set(set_name) if "text" in e]
    dups = [t for t, c in Counter(texts).items() if c > 1]
    assert not dups, f"{set_name} text 중복: {dups}"


# ── 4. must_pass 슬롯 커버리지 ─────────────────────────────────────────────

def test_must_pass_slot_minimum():
    entries = _load_set("must_pass")
    slot_counts = Counter(e["slot"] for e in entries if "slot" in e)
    # HateCheck 슬롯 + 자체 jamo_boundary 슬롯: 각 ≥5 (06 §1 '슬롯당 최소 5').
    for slot in HATECHECK_SLOTS:
        assert slot_counts.get(slot, 0) >= 5, (
            f"슬롯 {slot} 항목 {slot_counts.get(slot, 0)}개 < 최소 5"
        )


def test_must_pass_every_queue_term_has_f8():
    """큐 19개 용어 전부 F8(동음이의어) 또는 jamo_boundary 무해 용례 ≥1 (term_ref 기준)."""
    entries = _load_set("must_pass")
    covered = {
        e.get("term_ref")
        for e in entries
        if e.get("slot") in ("F8", "jamo_boundary")
    }
    missing = [t for t in QUEUE_TERMS if t not in covered]
    assert not missing, f"F8 동음이의어 무해 용례 누락 용어: {missing}"


def test_must_pass_grade_values_valid():
    entries = _load_set("must_pass")
    for i, e in enumerate(entries):
        grade = e.get("grade")
        assert grade in VALID_GRADES, f"must_pass[{i}] grade 비허용값: {grade!r}"


def test_must_pass_expected_empty():
    """must_pass는 무해 입력 — expected는 항상 빈 배열(어떤 매칭도 기대 안 함)."""
    for i, e in enumerate(_load_set("must_pass")):
        assert e["expected"] == [], f"must_pass[{i}] expected가 비어있지 않음: {e['expected']}"


# ── 5. must_catch 분량·severity 5 ──────────────────────────────────────────

def test_must_catch_volume():
    entries = _load_set("must_catch")
    assert len(entries) >= 40, f"must_catch {len(entries)}개 < 40 (브리프 최소치)"


def test_must_catch_has_all_severity5_terms():
    """severity 5 용어(운지·응디·노알라·삼일한)는 must_catch에 정착 용례로 포함."""
    entries = _load_set("must_catch")
    sev5_surfaces = set()
    for e in entries:
        if e.get("severity") == 5:
            sev5_surfaces.update(e["expected"])
    for surf in ("운지", "응디", "노알라", "삼일한"):
        assert surf in sev5_surfaces, f"severity 5 용어 '{surf}' must_catch 정착 용례 누락"


def test_must_catch_incident_sample_texts_present():
    """8건 incident sample_text 실문구가 must_catch에 포함되어야 한다(최우선 요구)."""
    texts = {e["text"] for e in _load_set("must_catch")}
    required = {
        "노무한 박수",
        "탱크 데이 5/18 · 책상에 탁",
        "(들켰노...)",
        "전라도 여행 갈 땐 여권 대신 수저 챙기세요",
        "보이루",
    }
    missing = required - texts
    assert not missing, f"incident 실문구 누락: {missing}"


# ── 6. evasion 분량·수렴 불변식 ────────────────────────────────────────────

def test_evasion_volume():
    entries = _load_set("evasion")
    # 큐 용어(텍스트형 18+) × 변형 종류 자연 분량.
    assert len(entries) >= 40, f"evasion {len(entries)}개 < 40"


def test_evasion_convergence_invariant():
    """verified_convergence=true 항목은 정규화 결과에 surface 키가 부분문자열로
    포함되어야 한다 (normalizer만으로 복원 가능함을 자산 단에서 보장)."""
    for i, e in enumerate(_load_set("evasion")):
        if e.get("verified_convergence") is True:
            norm = normalize(e["text"])[0]
            for surf in e["expected"]:
                key = normalized_key(surf)
                assert key in norm, (
                    f"evasion[{i}] 수렴 주장 위반: '{surf}' 키({key})가 "
                    f"정규화 결과({norm})에 없음"
                )


def test_evasion_expected_nonempty():
    """evasion은 회피 입력 — 반드시 복원 기대 surface가 있어야 한다."""
    for i, e in enumerate(_load_set("evasion")):
        assert e["expected"], f"evasion[{i}] expected 비어있음"
