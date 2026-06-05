"""변형 생성기 단위/속성 테스트 (docs/06-test-plan.md §2.1).

핵심 불변식:
  - 왕복(M1 형태): jamo 변형은 normalized_key(variant)==normalized_key(surface)로
    수렴해야 한다 — 이게 깨지면 1차 매칭(AC)이 깨진다.
  - chosung/leet: 자체 normalized_key가 결정적이고 비어 있지 않다(별도 키로 매칭).
  - 결정성: 같은 입력 → 같은 순서·같은 결과(두 번 호출 동일).
  - 상한: leet 변형 수 ≤ LEET_MAX_VARIANTS.
  - 무예외: 임의 한글/유니코드 입력.
  - 명시 케이스: '시발'(leet '시1발'), '운지'(chosung 'ㅇㅈ'), 혼합 '운G'.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from noise_checker.normalizer import normalized_key
from noise_checker.variants import (
    LEET_MAX_VARIANTS,
    Variant,
    generate_variants,
)

# 한글 음절 위주 + 자모/ASCII 혼합 표본.
_hangul_term = st.text(
    alphabet=st.one_of(
        st.characters(min_codepoint=0xAC00, max_codepoint=0xD7A3),  # 음절
        st.characters(min_codepoint=0x3131, max_codepoint=0x3163),  # 호환 자모
        st.characters(min_codepoint=0x0041, max_codepoint=0x007A),  # 라틴
        st.sampled_from("운지시발병신 0"),
    ),
    min_size=1,
    max_size=12,
)

_any_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), min_codepoint=0, max_codepoint=0x10FFFF),
    max_size=20,
)


# --------------------------------------------------------------------------
# 왕복 불변식 (가장 중요)
# --------------------------------------------------------------------------
@given(_hangul_term)
@settings(max_examples=600)
def test_jamo_roundtrip_converges(surface: str) -> None:
    """jamo 변형은 surface와 같은 정규화 키로 수렴한다.

    normalizer가 음절을 호환 자모로 분해하므로, 자모분리 표기는 정규화 후
    surface와 동일 키여야 한다(매칭 정합의 핵심).
    """
    surf_key = normalized_key(surface)
    for v in generate_variants(surface):
        if v.kind == "jamo":
            assert normalized_key(v.variant) == surf_key


@given(_hangul_term)
@settings(max_examples=600)
def test_chosung_leet_keys_deterministic_nonempty(surface: str) -> None:
    """chosung/leet 변형의 자체 normalized_key는 비어 있지 않고 결정적이다."""
    for v in generate_variants(surface):
        if v.kind in ("chosung", "leet"):
            k1 = normalized_key(v.variant)
            k2 = normalized_key(v.variant)
            assert k1 == k2
            assert k1 != ""


# --------------------------------------------------------------------------
# 결정성·무예외·상한
# --------------------------------------------------------------------------
@given(_any_text)
@settings(max_examples=600)
def test_no_exception_arbitrary_input(text: str) -> None:
    generate_variants(text)


@given(_hangul_term)
@settings(max_examples=600)
def test_deterministic(surface: str) -> None:
    a = generate_variants(surface)
    b = generate_variants(surface)
    assert a == b  # 같은 순서·같은 dataclass 값


@given(_hangul_term)
@settings(max_examples=600)
def test_leet_cap_respected(surface: str) -> None:
    leet = [v for v in generate_variants(surface) if v.kind == "leet"]
    assert len(leet) <= LEET_MAX_VARIANTS


@given(_hangul_term)
@settings(max_examples=600)
def test_no_self_and_no_duplicate_variant(surface: str) -> None:
    variants = generate_variants(surface)
    seen = [v.variant for v in variants]
    assert surface not in seen  # 자기 자신은 변형이 아님
    assert len(seen) == len(set(seen))  # variant 문자열 중복 없음


@given(_hangul_term)
@settings(max_examples=300)
def test_kind_order_jamo_chosung_leet(surface: str) -> None:
    """kind 순서 규약: jamo → chosung → leet (각 kind는 한 번에 묶여 등장)."""
    order = {"jamo": 0, "chosung": 1, "leet": 2}
    ranks = [order[v.kind] for v in generate_variants(surface)]
    assert ranks == sorted(ranks)


# --------------------------------------------------------------------------
# 명시 케이스
# --------------------------------------------------------------------------
def test_empty_input() -> None:
    assert generate_variants("") == []


def test_non_hangul_input_yields_nothing_relevant() -> None:
    # 한글이 없으면 jamo/chosung은 surface와 같아져 제외, leet도 없음.
    assert generate_variants("abc123") == []


def test_sibal_jamo_and_chosung_and_leet() -> None:
    variants = generate_variants("시발")
    kinds = {v.kind: v.variant for v in variants}
    # jamo 전체 분해
    assert kinds["jamo"] == "ㅅㅣㅂㅏㄹ"
    # chosung
    assert kinds["chosung"] == "ㅅㅂ"
    # leet '시1발' 포함
    leet_set = {v.variant for v in variants if v.kind == "leet"}
    assert "시1발" in leet_set
    # 왕복: jamo는 surface와 수렴
    assert normalized_key("ㅅㅣㅂㅏㄹ") == normalized_key("시발")


def test_unji_chosung() -> None:
    variants = generate_variants("운지")
    chosung = [v.variant for v in variants if v.kind == "chosung"]
    assert chosung == ["ㅇㅈ"]


def test_mixed_unji_g() -> None:
    # 혼합 '운G': 한글만 자모/초성 처리, 'G'는 보존.
    variants = generate_variants("운G")
    kinds = {v.kind: v.variant for v in variants}
    assert kinds["jamo"] == "ㅇㅜㄴG"
    assert kinds["chosung"] == "ㅇG"
    # leet: 초성 ㅇ→0/o 치환형 존재
    leet_set = {v.variant for v in variants if v.kind == "leet"}
    assert "0ㅜㄴG" in leet_set


def test_variant_is_frozen_dataclass() -> None:
    v = Variant(variant="ㅅㅂ", kind="chosung")
    assert v.variant == "ㅅㅂ"
    assert v.kind == "chosung"
