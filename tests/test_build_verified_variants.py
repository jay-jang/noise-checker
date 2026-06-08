"""verified 변형 생성·분류 도구 테스트 (M2).

검증 대상:
  - 왕복(매칭 가능) 불변식: verified로 분류된 모든 변형은 kind별 정의를 만족한다
    (jamo는 surface 키 수렴, leet/chosung은 비어 있지 않은 자기 키). 대상 용어 전수.
  - FP 분류: chosung 2자는 reject, ≥3자 FP-safe는 verified+context_required.
    명시 케이스(2자 reject·4자 accept) + 길이 게이트 일반.
  - 결정성·게이트 정합(verified는 FP 충돌 0).
"""

from __future__ import annotations

import json

from scripts.build_verified_variants import (
    CHOSUNG_MIN_LEN,
    _active_terms,
    _classify_variant,
    _common_key_index,
    classify_terms,
)
from scripts.variant_fp_sim import COMMON_WORDS

from noise_checker.normalizer import normalized_key
from noise_checker.variants import generate_variants


def _classify_one(surface: str, term_id: int, variant: str, kind: str):
    return _classify_variant(
        surface, term_id, variant, kind,
        normalized_key(surface), _common_key_index(),
    )


# --- 왕복(매칭 가능) 불변식 — 대상 용어 전수 --------------------------------
def test_verified_roundtrip_invariant_all_active_terms() -> None:
    """verified 분류된 모든 변형이 kind별 왕복 불변식을 만족한다(전수)."""
    rows = classify_terms(_active_terms())
    verified = [r for r in rows if r.decision == "verified"]
    assert verified, "verified 변형이 하나도 없으면 분류 자체가 의심"
    for r in verified:
        # 키는 비어 있지 않다(매칭 가능).
        assert r.normalized_key, f"빈 키 verified: {r}"
        assert r.normalized_key == normalized_key(r.variant)
        if r.variant_kind == "jamo":
            # jamo는 surface 키로 수렴(AC 1차 매칭 정합).
            assert r.normalized_key == normalized_key(r.surface)


def test_classified_variant_keys_match_generator() -> None:
    """분류 행의 variant/kind가 generate_variants 산출과 1:1 대응한다(누락·날조 없음)."""
    terms = _active_terms()
    rows = classify_terms(terms)
    expected: list[tuple[str, str, str]] = []
    for t in terms:
        for v in generate_variants(t["surface"]):
            expected.append((t["surface"], v.variant, v.kind))
    actual = [(r.surface, r.variant, r.variant_kind) for r in rows]
    assert actual == expected


# --- FP 분류: chosung 길이 게이트 (명시 케이스) ------------------------------
def test_chosung_two_char_rejected() -> None:
    # '운지' chosung 'ㅇㅈ'(2자) → reject (v1 80.2% 충돌 근거).
    r = _classify_one("운지", 58, "ㅇㅈ", "chosung")
    assert r.decision == "reject"
    assert r.context_required is False
    assert "2자" in r.reason


def test_chosung_four_char_accepted_with_context() -> None:
    # 4자 chosung(FP-safe) → verified + context_required=true.
    # '보슬아치' chosung 'ㅂㅅㅇㅊ'(4자).
    chosung = next(
        v.variant for v in generate_variants("보슬아치") if v.kind == "chosung"
    )
    assert len(chosung) == 4
    r = _classify_one("보슬아치", 31, chosung, "chosung")
    assert r.decision == "verified"
    assert r.context_required is True


def test_chosung_three_char_is_min_accept_boundary() -> None:
    # 경계: 정확히 CHOSUNG_MIN_LEN(3)자 FP-safe chosung은 verified.
    chosung = next(
        v.variant for v in generate_variants("삼일한") if v.kind == "chosung"
    )
    assert len(chosung) == CHOSUNG_MIN_LEN
    r = _classify_one("삼일한", 17, chosung, "chosung")
    assert r.decision == "verified"
    assert r.context_required is True


# --- FP 분류: jamo/leet ------------------------------------------------------
def test_jamo_verified_and_not_context_required() -> None:
    jamo = next(v.variant for v in generate_variants("운지") if v.kind == "jamo")
    r = _classify_one("운지", 58, jamo, "jamo")
    assert r.decision == "verified"
    assert r.context_required is False


def test_fp_collision_rejects_variant() -> None:
    # 일반어 코퍼스에 있는 단어를 변형으로 위장하면 FP 충돌로 reject되는지(게이트 동작).
    common = COMMON_WORDS[0]  # '사람'
    jamo = next(
        (v.variant for v in generate_variants(common) if v.kind == "jamo"), None
    )
    assert jamo is not None
    r = _classify_one(common, 999, jamo, "jamo")
    # jamo는 surface 키로 수렴하므로 surface 자체가 일반어면 충돌 → reject.
    assert r.decision == "reject"
    assert "FP 충돌" in r.reason


# --- 게이트 정합 / 결정성 ----------------------------------------------------
def test_no_verified_variant_collides_with_common() -> None:
    """verified 변형은 일반어 키와 충돌하지 않는다(FP-safe 보장)."""
    common = set(_common_key_index())
    for r in classify_terms(_active_terms()):
        if r.decision == "verified":
            assert r.normalized_key not in common, f"verified인데 FP 충돌: {r}"


def test_classification_deterministic() -> None:
    a = classify_terms(_active_terms())
    b = classify_terms(_active_terms())
    assert a == b


def test_all_two_char_chosung_rejected() -> None:
    """초성 2자 chosung은 (FP-safe 여부 무관) 전부 reject."""
    rows = [
        r for r in classify_terms(_active_terms())
        if r.variant_kind == "chosung" and len(r.variant) <= 2
    ]
    assert rows, "2자 chosung 표본이 없으면 길이 게이트 검증 불가"
    assert all(r.decision == "reject" for r in rows)


# --- 산출물 형식 -------------------------------------------------------------
def test_output_rows_have_required_fields() -> None:
    rows = classify_terms(_active_terms())
    for r in rows:
        assert r.decision in ("verified", "reject")
        assert r.variant_kind in ("jamo", "chosung", "leet")
        assert isinstance(r.context_required, bool)
        # reject는 사유가 비어 있지 않다.
        assert r.reason


def test_active_terms_file_loads() -> None:
    terms = _active_terms()
    assert len(terms) >= 1
    for t in terms:
        assert isinstance(t["surface"], str) and t["surface"]
        assert isinstance(t["term_id"], int)


def test_active_terms_json_is_valid() -> None:
    # 입력 파일이 직접 파싱 가능한 JSON인지(스크립트 외 경로 회귀).
    from scripts.build_verified_variants import REPO_ROOT

    raw = (REPO_ROOT / "data" / "variants" / "active-terms.json").read_text("utf-8")
    json.loads(raw)
