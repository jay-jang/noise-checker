"""변형 적대적 검증 v2 — verified 변형(jamo/leet/chosung)의 미탐·오탐 공격.

생성 에이전트(feat/m2-verified-variants-chosung-cap)가 'FP-safe·verified 권고'한
변형을 **반박하려는 자세**로 검증한다. 두 축을 본다:

  1. 매칭(미탐 방지): 각 종류의 표본 변형을 실제로 타이핑하면 엔진이 매치하고,
     chosung은 상한 review로 캡되며(단독 매칭 위험 잔존), reject된 chosung 2자
     키는 단독 매칭되지 않는다.
  2. 오탐(억울한 차단): 무해 문장에 변형 키가 부분/전체 일치할 때 엔진이
     무해 문장을 잡는지 — 특히 **chosung 키가 일반 chosung 약어와 충돌**하는
     경우(예 `ㄱㅊㄴ`=괜찮네, `ㅁㅊㄷ`=미쳤다). 충돌이 확인된 키는 광역 FP
     리포트(구조화 보고 flagged)로 올린다.

픽스처: conftest의 release_test 엔진. release_test/terms.json에는 삼일한의
chosung 변형 `ㅅㅇㅎ`·leet 변형 `삼일1한`이 적재돼 있어 빌드 없이 종류별
분기(0.7 캡 / 0.9 / 1.0)를 검증할 수 있다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from noise_checker.engine import Engine, compiled_normalizer_version
from noise_checker.normalizer import normalized_key

# 광역 FP 재검에서 일반 chosung 표기와 충돌이 확인된 surface(3자 키). 공유
# release_test 픽스처에는 적재하지 않고(픽스처 비대화 방지), 이 모듈 전용
# 아티팩트로만 로드해 '무해 chosung 문장이 잡힌다'는 사실을 고정한다.
_FP_CHOSUNG_TERMS = [
    # (surface, severity, ambiguity, chosung_key)
    ("김치녀", 4, "ambiguous", "ㄱㅊㄴ"),     # = 괜찮네/괜찮나/김치냐
    ("멍청도", 4, "unambiguous", "ㅁㅊㄷ"),    # = 미쳤다/맞췄다/민초단
    ("숨쉴한", 5, "unambiguous", "ㅅㅅㅎ"),    # = 수술했/생생했/신선했
]


@pytest.fixture(scope="module")
def fp_engine(tmp_path_factory: pytest.TempPathFactory) -> Engine:
    """광역 FP 충돌 chosung 변형을 적재한 전용 엔진(공유 픽스처와 분리)."""
    terms = [
        {
            "term_id": 1000 + i,
            "surface": surface,
            "term_kind": "word",
            "normalized_key": normalized_key(surface),
            "severity": sev,
            "ambiguity": amb,
            "status": "active",
            "release_policy": "general",
            "categories": ["test"],
            "safe_contexts": [],
            "is_dogwhistle_marker": False,
            "variants": [
                {"surface": key, "normalized_key": key, "variant_kind": "chosung"}
            ],
            "combination_rules": [],
        }
        for i, (surface, sev, amb, key) in enumerate(_FP_CHOSUNG_TERMS)
    ]
    d = tmp_path_factory.mktemp("fp_release")
    (d / "terms.json").write_text(json.dumps(terms, ensure_ascii=False), encoding="utf-8")
    (d / "kiwi_user_dict.tsv").write_text(
        "\n".join(f"{s}\tNNP" for s, *_ in _FP_CHOSUNG_TERMS) + "\n", encoding="utf-8"
    )
    manifest = {
        "release_version": "fp-adv",
        "contract_version": "1.1",
        "normalizer_code_version": compiled_normalizer_version(),
        "term_count": len(terms),
        "variant_count": len(terms),
        "checksums": {},
    }
    (d / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return Engine.load(Path(d))


# === 1. 매칭(미탐 방지) — 종류별 표본 변형이 실제로 매치된다 ===================
def test_leet_variant_matches_with_confidence_0_9(engine: Engine) -> None:
    # leet 변형 `삼일1한`은 verified 변형 → confidence 0.9로 surface 용어에 매치.
    matches = engine.check("어제 삼일1한 봤다")["matches"]
    leet = [m for m in matches if m["match_confidence"] == 0.9]
    assert leet and all(m["surface"] == "삼일한" for m in leet)


def test_chosung_variant_matches_and_capped(engine: Engine) -> None:
    # chosung 변형 `ㅅㅇㅎ`(삼일한)은 매치하되 0.7 + flag + 상한 review(revise 금지).
    matches = engine.check("ㅅㅇㅎ ㄱㄱ")["matches"]
    cho = [m for m in matches if "chosung_variant" in m["flags"]]
    assert cho, "chosung 변형이 매치되지 않음(미탐)"
    for m in cho:
        assert m["match_confidence"] == 0.7
        assert m["usage_recommendation"] in ("monitor", "review_recommended")
        assert m["usage_recommendation"] != "revise_recommended"


def test_jamo_variant_converges_to_surface_key() -> None:
    # jamo 변형은 정규화로 surface와 **같은 키로 수렴**한다(별도 행 불요 — 중복).
    # 행으로 적재해도 무해하나, normalizer 수렴이 이미 같은 매치를 만든다.
    pairs = {
        "운지": "ㅇㅜㄴㅈㅣ",
        "된장녀": "ㄷㅚㄴㅈㅏㅇㄴㅕ",
        "삼일한": "ㅅㅏㅁㅇㅣㄹㅎㅏㄴ",
        "한남": "ㅎㅏㄴㄴㅏㅁ",
    }
    for surface, jamo in pairs.items():
        assert normalized_key(jamo) == normalized_key(surface)


# === 2. reject된 chosung 2자 키는 단독 매칭되지 않는다(task 3c) ================
# v1 결론: chosung 2자 키는 일반어와 80.2% 충돌 → 단독 매칭 금지(reject).
# terms.json에 적재되지 않았으므로 엔진이 이 키를 chosung 변형으로 잡으면 안 된다.
_REJECTED_CHOSUNG_2 = ["ㅇㄷ", "ㅎㄴ", "ㅁㅊ", "ㅎㅇ", "ㄴㅁ", "ㅈㅈ", "ㅂㅅ", "ㅇㅈ"]


@pytest.mark.parametrize("key", _REJECTED_CHOSUNG_2)
def test_rejected_chosung_2char_does_not_match(engine: Engine, key: str) -> None:
    matches = engine.check(f"{key} 테스트")["matches"]
    assert not [m for m in matches if "chosung_variant" in m["flags"]], (
        f"reject된 chosung 2자 {key!r}가 단독 매칭됨 — v1 80.2% 충돌 결론 위반"
    )


# === 3. 오탐(억울한 차단) — chosung 키가 일반 chosung 약어와 충돌 =============
# 광역 FP 재검 결과(아래 surface 매핑): 일부 verified chosung 키는 흔한 무해
# chosung 표기와 정확히 일치한다. 이 테스트는 '엔진이 무해 문장을 잡는다'는
# **사실을 고정**한다(=오탐 잔존 증거). context_required=true·review 캡으로도
# 매치 자체는 제거되지 않으므로, 메인 세션은 이 surface들의 chosung 변형을
# verified에서 제외(또는 별도 게이트)할지 판단해야 한다.
#
# 형식: (무해 chosung 문장, 실제로 잡히는 surface). 충돌 근거는 reason 주석.
_BENIGN_CHOSUNG_FP = [
    ("ㄱㅊㄴ 그 정도면 됐어", "김치녀"),   # ㄱㅊㄴ = 괜찮네/괜찮나/김치냐
    ("이거 ㄱㅊㄴ?", "김치녀"),             # 괜찮나?
    ("와 ㅁㅊㄷ 진짜 대박", "멍청도"),       # ㅁㅊㄷ = 미쳤다/맞췄다/민초단
    ("시험 ㅁㅊㄷ 잘봤어?", "멍청도"),       # 맞췄다?
    ("어제 ㅅㅅㅎ 친구 만났어", "숨쉴한"),   # ㅅㅅㅎ = 수술했/생생했/신선했
]


@pytest.mark.parametrize("text,surface", _BENIGN_CHOSUNG_FP)
def test_benign_chosung_phrase_is_false_positive(
    fp_engine: Engine, text: str, surface: str
) -> None:
    # 적대적 사실 고정: 무해 chosung 문장이 chosung 변형으로 매치된다(오탐).
    # 매치는 review 이하로 캡되지만 **제거되지는 않는다** — 이 잔존이 flagged 사유.
    matches = fp_engine.check(text)["matches"]
    hits = [m for m in matches if m["surface"] == surface and "chosung_variant" in m["flags"]]
    assert hits, f"광역 FP 표본 {text!r}이 더는 {surface}로 잡히지 않음 — 매핑 갱신 필요"
    # 잔존 오탐은 절대 revise가 아니어야 한다(캡 불변식 — 그나마의 방어선).
    assert all(m["usage_recommendation"] != "revise_recommended" for m in hits)


# === 4. leet 키는 광역 일반어와 충돌하지 않는다(숫자/leet 문자 보유) ===========
# leet 변형 키는 '1'/'0' 등 숫자를 포함해 정규화된 일반어 키와 구조적으로 다르다.
# 무해 문장(숫자 없는 일상어)에는 leet 변형이 매치되지 않아야 한다.
_BENIGN_NO_LEET = ["운지법을 배웠다", "삼일한약방에 갔다", "홍어무침 맛있다", "병들어 신음했다"]


@pytest.mark.parametrize("text", _BENIGN_NO_LEET)
def test_benign_text_no_leet_false_positive(engine: Engine, text: str) -> None:
    matches = engine.check(text)["matches"]
    assert not [m for m in matches if m["match_confidence"] == 0.9], (
        f"무해 문장 {text!r}에 leet 변형(0.9)이 오탐으로 매치됨"
    )
