"""정규화 모듈 속성/단위 테스트 (docs/06-test-plan.md §2.1).

- 멱등성: normalize(norm_text)[0] == norm_text
- 무예외: 임의 유니코드(서로게이트 제외) 입력에 예외 없음
- 오프셋 불변식 (02 §4.1): src_offset 단조 비감소,
  len(src_offset) == len(norm_text), 모든 값이 0 <= v < len(원문)
- NFKC 일관성: normalize(x)[0] == normalize(NFKC(x))[0]
- normalized_key(x) == normalize(x)[0]
- 오프셋 의미 검증(왕복): norm_text 구간을 src_offset으로 원문 구간으로
  환원하면 그 원문 부분 문자열의 normalize 결과가 그 구간과 일치
- 명시 케이스: '운지', 제로폭 삽입, 전각, 혼합, 빈 문자열, 자모 단독
"""

from __future__ import annotations

import unicodedata

from hypothesis import given, settings
from hypothesis import strategies as st

from noise_checker.normalizer import (
    NORMALIZER_CODE_VERSION,
    normalize,
    normalized_key,
)

# 서로게이트(U+D800~U+DFFF)는 파이썬 str에 들어갈 수 없으므로 제외한다.
# 그 외 전체 유니코드 평면을 표본으로 삼는다.
_unicode_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),  # surrogate
        min_codepoint=0,
        max_codepoint=0x10FFFF,
    ),
    max_size=40,
)

# 한글 음절·자모를 더 자주 섞어 자모 분해/경계 케이스를 강하게 친다.
_hangul_heavy = st.text(
    alphabet=st.one_of(
        st.characters(min_codepoint=0xAC00, max_codepoint=0xD7A3),  # 음절
        st.characters(min_codepoint=0x3131, max_codepoint=0x3163),  # 호환 자모
        st.characters(min_codepoint=0x0020, max_codepoint=0x007E),  # ASCII
        st.sampled_from("​﻿‍­운지시발ＡＢ１２가나"),
    ),
    max_size=40,
)


# --------------------------------------------------------------------------
# 속성 테스트
# --------------------------------------------------------------------------
@given(_unicode_text)
@settings(max_examples=600)
def test_no_exception_on_arbitrary_unicode(text: str) -> None:
    # 무예외: 임의 유니코드 입력에 예외가 없어야 한다.
    normalize(text)
    normalized_key(text)


@given(st.one_of(_unicode_text, _hangul_heavy))
@settings(max_examples=600)
def test_idempotent(text: str) -> None:
    # 멱등성: 한 번 정규화한 결과를 다시 정규화해도 동일해야 한다.
    norm_text, _ = normalize(text)
    again, _ = normalize(norm_text)
    assert again == norm_text


@given(st.one_of(_unicode_text, _hangul_heavy))
@settings(max_examples=600)
def test_offset_invariants(text: str) -> None:
    # 오프셋 불변식 (02 §4.1).
    norm_text, off = normalize(text)
    # 길이 일치
    assert len(off) == len(norm_text)
    # 단조 비감소
    assert all(off[i] <= off[i + 1] for i in range(len(off) - 1))
    # 범위: 0 <= v < len(원문)
    for v in off:
        assert 0 <= v < len(text)


@given(st.one_of(_unicode_text, _hangul_heavy))
@settings(max_examples=600)
def test_nfkc_consistency(text: str) -> None:
    # NFKC 일관성: NFKC 선적용 여부와 무관하게 결과가 같아야 한다.
    a, _ = normalize(text)
    b, _ = normalize(unicodedata.normalize("NFKC", text))
    assert a == b


@given(st.one_of(_unicode_text, _hangul_heavy))
@settings(max_examples=600)
def test_normalized_key_matches_normalize(text: str) -> None:
    # normalized_key(x) == normalize(x)[0]
    assert normalized_key(text) == normalize(text)[0]


@given(_hangul_heavy)
@settings(max_examples=600)
def test_offset_roundtrip_semantics(text: str) -> None:
    """오프셋 의미 검증: norm_text의 임의 구간 [a:b)를 src_offset으로 원문
    구간으로 환원했을 때, 그 원문 부분 문자열의 normalize 결과는 norm_text
    구간을 **부분 문자열로 포함**해야 한다.

    환원 구간이 음절 경계에 정렬되면 정확히 일치하고, 자모 중간을 가르는
    경우에도 src_offset이 가리키는 원문 음절 전체가 환원되므로 원문 구간의
    normalize 결과는 항상 norm_text[a:b]를 포함한다(span의 원문 좌표 환원
    정확성 보장 — 02 §4.1 음절 경계 스냅 규칙의 전제).
    """
    norm_text, off = normalize(text)
    n = len(norm_text)
    if n == 0:
        return
    # 결정적으로 몇몇 구간을 검사: 전체, 앞절반, 뒤절반, 단일 코드포인트들
    spans = [(0, n), (0, n // 2 or 1), (n // 2, n)]
    spans += [(i, i + 1) for i in range(0, n, max(1, n // 4))]
    for a, b in spans:
        if a >= b:
            continue
        src_a = off[a]
        src_b = off[b - 1] + 1
        sub_norm, _ = normalize(text[src_a:src_b])
        assert norm_text[a:b] in sub_norm


@given(st.one_of(_unicode_text, _hangul_heavy))
@settings(max_examples=400)
def test_offset_reconstructs_each_codepoint(text: str) -> None:
    """각 norm 코드포인트를 원문 단일 인덱스에서 환원했을 때, 그 원문 문자
    하나의 normalize 결과가 해당 norm 코드포인트를 포함해야 한다.
    (자모 분해 1→N: 원문 음절 1자 → 자모 N개 모두 포함)."""
    norm_text, off = normalize(text)
    for i, nch in enumerate(norm_text):
        src_i = off[i]
        sub, _ = normalize(text[src_i : src_i + 1])
        assert nch in sub


# --------------------------------------------------------------------------
# 명시 케이스
# --------------------------------------------------------------------------
def test_unji_decomposes_to_compat_jamo() -> None:
    # '운지' → 'ㅇㅜㄴㅈㅣ' (호환 자모), 오프셋은 음절 단위로 반복.
    norm_text, off = normalize("운지")
    assert norm_text == "ㅇㅜㄴㅈㅣ"
    # 모두 호환 자모 영역(U+3131~U+3163)
    assert all(0x3131 <= ord(c) <= 0x3163 for c in norm_text)
    # '운'(0)에서 3자모, '지'(1)에서 2자모
    assert off == [0, 0, 0, 1, 1]


def test_standalone_jamo_input() -> None:
    # 자모 단독 입력 'ㅅㅂ'은 호환 자모 그대로 유지되어야 키가 수렴한다.
    norm_text, off = normalize("ㅅㅂ")
    assert norm_text == "ㅅㅂ"
    assert all(0x3131 <= ord(c) <= 0x3163 for c in norm_text)
    assert off == [0, 1]


def test_jamo_variant_converges_with_syllable() -> None:
    # 자모 분리 변형('ㅅㅣㅂㅏㄹ')과 음절형('시발')이 같은 키로 수렴.
    assert normalized_key("시발") == normalized_key("ㅅㅣㅂㅏㄹ")
    # 초성/종성 동일 음소도 같은 호환 자모로 수렴 (받침 ㄴ vs 초성 ㄴ)
    # '안'(받침 ㄴ) → ㅇㅏㄴ, 'ㄴ' 단독 → ㄴ : 종성 ㄴ과 호환 ㄴ 동일 코드포인트
    an, _ = normalize("안")
    assert an[-1] == "ㄴ"


def test_zero_width_insertion_is_removed_with_correct_offsets() -> None:
    # 제로폭(U+200B) 삽입: norm_text 불변, 오프셋은 삽입 위치를 건너뛴다.
    base, base_off = normalize("운지")
    zwsp, zwsp_off = normalize("운​지")  # 인덱스 1에 ZWSP
    assert zwsp == base == "ㅇㅜㄴㅈㅣ"
    # '지' 유래 인덱스가 ZWSP만큼 밀려 2를 가리킨다.
    assert zwsp_off == [0, 0, 0, 2, 2]
    # 모든 오프셋이 ZWSP 인덱스(1)를 가리키지 않음
    assert 1 not in zwsp_off


def test_bom_feff_removed() -> None:
    # U+FEFF(BOM/제로폭 no-break space)도 제거된다.
    norm_text, off = normalize("a﻿b")
    assert norm_text == "ab"
    assert off == [0, 2]


def test_fullwidth_latin_and_digits() -> None:
    # 전각 영문/숫자 → NFKC로 반각·소문자화.
    norm_text, off = normalize("ＡＢＣ１２３")
    assert norm_text == "abc123"
    # 1:1 매핑이므로 오프셋은 0..5
    assert off == [0, 1, 2, 3, 4, 5]


def test_hangul_latin_mixed() -> None:
    # 한글+라틴 혼합: 라틴은 소문자, 한글은 자모 분해.
    norm_text, off = normalize("A운")
    assert norm_text == "aㅇㅜㄴ"
    # 'a'는 원문 0, 자모 3개는 원문 1
    assert off == [0, 1, 1, 1]


def test_empty_string() -> None:
    # 빈 문자열.
    assert normalize("") == ("", [])
    assert normalized_key("") == ""


def test_syllable_boundary_seam_offset_alignment() -> None:
    """음절 경계 이음새 케이스: '운지'의 ㄴ|ㅈ 이음새를 우연히 포함하는 입력의
    오프셋이 원문 음절 경계로 정확히 정렬되는지 (06 §1 자모 경계 오정렬 슬롯).
    '안주' → ㅇㅏㄴㅈㅜ : ㄴ(받침, 원문0) | ㅈ(초성, 원문1) 경계 확인."""
    norm_text, off = normalize("안주")
    assert norm_text == "ㅇㅏㄴㅈㅜ"
    # ㄴ은 '안'(0)에서, ㅈ은 '주'(1)에서 유래 — 경계가 음절 경계와 정렬
    assert off == [0, 0, 0, 1, 1]
    seam = norm_text.index("ㄴ")
    assert off[seam] == 0 and off[seam + 1] == 1


def test_combining_marks_removed_accent_preserved_when_precomposed() -> None:
    # NFKC가 결합 가능한 악센트는 단일 코드포인트로 합성 → 결합 기호가
    # 아니므로 유지된다(e + ◌́ → é). 분리된 결합 기호만 제거 대상.
    norm_text, _ = normalize("é")  # e + COMBINING ACUTE → é
    assert norm_text == "é"
    # 반면 결합 가능한 base가 없는 고립 결합 기호는 제거.
    only_mark, off = normalize("́")
    assert only_mark == ""
    assert off == []


def test_normalizer_code_version_is_stable_hash() -> None:
    # manifest 검증용 해시 상수: 64자리 hex(sha256).
    assert isinstance(NORMALIZER_CODE_VERSION, str)
    assert len(NORMALIZER_CODE_VERSION) == 64
    assert all(c in "0123456789abcdef" for c in NORMALIZER_CODE_VERSION)
