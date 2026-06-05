"""data/schema/*.json 계약 검증 — 메타스키마 유효성 + 픽스처 통과 + 음성 케이스 거부.

$ref(candidate-term) 해석은 referencing 로컬 레지스트리로만 처리한다 (네트워크 fetch 금지).
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCHEMA_DIR = DATA_DIR / "schema"
SEED_DIR = DATA_DIR / "seed"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _registry() -> Registry:
    """모든 로컬 스키마를 $id로 등록 — $ref는 이 레지스트리에서만 해석된다."""
    resources = []
    for schema_path in SCHEMA_DIR.glob("*.json"):
        schema = _load(schema_path)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


REGISTRY = _registry()


def _validator(schema_id: str) -> Draft202012Validator:
    schema = REGISTRY.get_or_retrieve(schema_id).value.contents
    return Draft202012Validator(schema, registry=REGISTRY)


# ── 1. 모든 스키마가 Draft 2020-12 메타스키마로 유효한가 ──────────────────────

@pytest.mark.parametrize("schema_path", sorted(SCHEMA_DIR.glob("*.json")), ids=lambda p: p.name)
def test_schema_is_valid_metaschema(schema_path: Path):
    Draft202012Validator.check_schema(_load(schema_path))


# ── 2. 긍정: 픽스처가 해당 스키마를 통과하는가 ────────────────────────────────

def test_unji_term_passes_candidate_term():
    entry = _load(SEED_DIR / "example-term-unji.json")
    _validator("noise-checker/candidate-term").validate(entry)


@pytest.mark.parametrize(
    "fixture",
    ["example-payload-new-term-unji.json", "example-payload-incident-tankday.json"],
)
def test_payload_fixtures_pass(fixture: str):
    payload = _load(SEED_DIR / fixture)
    _validator("noise-checker/candidate-payload").validate(payload)


# ── 3. 음성: 계약 위반은 거부되어야 한다 ──────────────────────────────────────

def _new_term_payload() -> dict:
    return copy.deepcopy(_load(SEED_DIR / "example-payload-new-term-unji.json"))


def test_new_term_without_negative_examples_rejected():
    payload = _new_term_payload()
    del payload["payload"]["negative_examples"]
    v = _validator("noise-checker/candidate-payload")
    assert not v.is_valid(payload)


def test_number_kind_without_trigger_evidence_rejected():
    payload = _new_term_payload()
    inner = payload["payload"]
    inner["term_kind"] = "number"
    inner["surface"] = "18"
    # negative_examples는 있고 combination_rules도 채우지만 trigger_evidence 누락 → 거부
    inner["combination_rules"] = [
        {"trigger_kind": "co_occurrence", "base_severity": 1, "severity_delta": 3}
    ]
    v = _validator("noise-checker/candidate-payload")
    assert not v.is_valid(payload)


def test_number_kind_with_trigger_evidence_and_rules_passes():
    payload = _new_term_payload()
    inner = payload["payload"]
    inner["term_kind"] = "number"
    inner["surface"] = "18"
    inner["combination_rules"] = [
        {"trigger_kind": "co_occurrence", "base_severity": 1, "severity_delta": 3}
    ]
    inner["trigger_evidence"] = ["https://example.org/why-18-is-risky"]
    _validator("noise-checker/candidate-payload").validate(payload)


def test_golden_entry_without_text_or_image_rejected():
    entry = {
        "expected": [],
        "why": "동음이의어 무해 용례",
        "source": "https://example.org/x",
        "added_at": "2026-06-05T00:00:00Z",
    }
    v = _validator("noise-checker/golden-entry")
    assert not v.is_valid(entry)


def test_golden_entry_with_text_passes():
    entry = {
        "text": "운지버섯은 면역에 좋다.",
        "expected": [],
        "why": "F8 동음이의어 — 잡으면 안 됨",
        "source": "https://example.org/unji-mushroom",
        "added_at": "2026-06-05T00:00:00Z",
        "set": "must_pass",
        "slot": "F8",
    }
    _validator("noise-checker/golden-entry").validate(entry)


def test_evidence_excerpt_over_300_chars_rejected():
    entry = _load(SEED_DIR / "example-term-unji.json")
    entry = copy.deepcopy(entry)
    entry["evidence"][0]["excerpt"] = "가" * 301
    v = _validator("noise-checker/candidate-term")
    assert not v.is_valid(entry)
