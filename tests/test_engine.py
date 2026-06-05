"""검사 엔진 테스트 (M2-B) — docs/03 §2 파이프라인·정책표 v1.

fixtures/release_test 아티팩트(손작성)를 conftest의 engine 픽스처로 로드한다.
케이스 출처: 작업 명세 + docs/06 §1 골든셋 슬롯(운지버섯·원조/안주·한남동).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from noise_checker.engine import Engine, compiled_normalizer_version
from tests.conftest import materialize_release


def _one(engine: Engine, text: str) -> dict:
    """매치가 정확히 1건인 케이스의 그 매치를 반환(편의)."""
    matches = engine.check(text)["matches"]
    assert len(matches) == 1, f"매치 1건 기대, 실제 {len(matches)}건: {matches}"
    return matches[0]


# --- 로드/버전 검증 ---------------------------------------------------------
def test_load_rejects_normalizer_version_mismatch(tmp_path: Path) -> None:
    # manifest의 normalizer_code_version이 코드와 다르면 ValueError로 거부한다.
    bad = materialize_release(tmp_path / "bad", normalizer_version="mismatch-xxx")
    with pytest.raises(ValueError, match="normalizer 버전 불일치"):
        Engine.load(bad)


def test_load_accepts_matching_version(release_dir: Path) -> None:
    eng = Engine.load(release_dir)
    assert eng.release_version == "2026.06.05-1"


def test_compiled_version_is_stable() -> None:
    assert compiled_normalizer_version() == compiled_normalizer_version()


# --- 정확 매칭 / 등급 -------------------------------------------------------
def test_exact_unambiguous_severe_is_revise(engine: Engine) -> None:
    # 삼일한: unambiguous sev5 → revise_recommended, confidence 1.0.
    m = _one(engine, "삼일한 하자")
    assert m["surface"] == "삼일한"
    assert m["usage_recommendation"] == "revise_recommended"
    assert m["match_confidence"] == 1.0
    assert m["context_score"] == 1.0
    assert m["risk_score"] == pytest.approx(1.0)
    assert m["span"] == {"start": 0, "end": 3}


def test_ambiguous_standalone_is_review_cap(engine: Engine) -> None:
    # 운지(ambiguous sev4) 단독 → review 상한(revise 금지).
    m = _one(engine, "운지 ㅋㅋ")
    assert m["surface"] == "운지"
    assert m["ambiguity"] == "ambiguous"
    assert m["usage_recommendation"] == "review_recommended"
    assert m["context_score"] == 0.5


# --- safe_contexts / 형태소 경계로 해소 -------------------------------------
def test_unjibeoseot_resolved_by_morpheme(engine: Engine) -> None:
    # "운지버섯"은 한 토큰 → 내부 '운지' 매치 폐기(형태소 경계). + safe_context.
    assert engine.check("운지버섯을 채취했다")["matches"] == []


def test_unji_with_safe_context_token_resolved(engine: Engine) -> None:
    # 띄어쓴 '운지'라도 ±20자 창에 safe_context('버섯')가 있으면 해소.
    assert engine.check("운지 같은 식용 버섯")["matches"] == []


def test_hannam_dong_realestate_resolved(engine: Engine) -> None:
    # "한남동 부동산"은 '한남동' 한 토큰 + safe_context → 해소.
    assert engine.check("한남동 부동산 시세 문의")["matches"] == []


def test_hannam_standalone_not_resolved(engine: Engine) -> None:
    # safe_context 없는 '한남' 단독은 매칭이 남는다(ambiguous → revise 불가).
    m = _one(engine, "저 한남 진짜 별로")
    assert m["surface"] == "한남"
    assert m["usage_recommendation"] != "revise_recommended"


# --- watchlist / number 조합 -------------------------------------------------
def test_watchlist_is_monitor(engine: Engine) -> None:
    # 탱크데이(watchlist) → 항상 monitor (불변식 ②).
    m = _one(engine, "탱크데이 행사 진행")
    assert m["usage_recommendation"] == "monitor"


def test_number_standalone_is_monitor(engine: Engine) -> None:
    # 503 단독(combination_rule 미충족) → monitor.
    m = _one(engine, "대통령 503 수감")
    assert m["surface"] == "503"
    assert "composite_unsatisfied" in m["flags"]
    assert m["usage_recommendation"] == "monitor"


def test_number_with_cooccurrence_satisfied(engine: Engine) -> None:
    # 503 + 삼일한 동시 출현 → 503의 co_occurrence 규칙 충족.
    result = engine.check("503 삼일한 동시 출현")
    by_surface = {m["surface"]: m for m in result["matches"]}
    assert "composite_satisfied" in by_surface["503"]["flags"]
    # 전체 등급은 삼일한(revise)이 최고.
    assert result["overall_recommendation"] == "revise_recommended"


# --- safe_context 셀프 해소 회귀 (버그 1) -----------------------------------
def test_doenjangnyeo_standalone_not_self_resolved(engine: Engine) -> None:
    # surface '된장녀'는 safe_context '된장'을 내포한다. 매치 스팬을 창에서
    # 제외하지 않으면 자기 매치가 셀프 해소돼 단독 surface조차 미탐된다.
    m = _one(engine, "된장녀")
    assert m["surface"] == "된장녀"
    assert m["span"] == {"start": 0, "end": 3}


def test_doenjangnyeo_resolved_by_outside_safe_token(engine: Engine) -> None:
    # 스팬 '밖'에 safe 토큰('된장')이 실제로 있으면 정상 해소된다.
    text = "점심엔 된장찌개를 끓였다 된장녀라니"
    assert engine.check(text)["matches"] == []


# --- pattern -----------------------------------------------------------------
def test_pattern_no_ending_matches(engine: Engine) -> None:
    # '~노?' 어미 pattern (term_kind='pattern') 정규식 경로.
    matches = engine.check("이걸 진짜 들켰노?")["matches"]
    surfaces = {m["matched_text"] for m in matches}
    assert any("노?" in s for s in surfaces)


def test_pattern_declarative_no_ending_matches(engine: Engine) -> None:
    # 평서문 종결 '들켰노...'도 pattern 정규식((.+)노[…]*$)이 잡는다.
    # 리터럴 surface('~노')를 컴파일하던 옛 경로는 이를 놓쳤다(버그 2).
    matches = engine.check("이건 들켰노...")["matches"]
    assert any(m["term_id"] == 4 for m in matches)
    # 별도 pattern 필드가 있으므로 폴백 플래그가 붙지 않는다.
    pat = next(m for m in matches if m["term_id"] == 4)
    assert "pattern_fallback_literal" not in pat["flags"]


def test_pattern_dialect_resolved_by_safe_context(engine: Engine) -> None:
    # '~노'는 경상도 방언 의문 종결어미와 동형 — safe_context 토큰('부산','사투리')이
    # 창에 있으면 해소돼 방언 화자 오인을 막는다.
    assert engine.check("부산 사투리로 어디 가노")["matches"] == []


def test_pattern_field_missing_falls_back_to_literal(tmp_path: Path) -> None:
    # pattern 필드가 없는(구버전) pattern term은 surface를 리터럴로 escape해
    # 폴백하고 매치에 'pattern_fallback_literal' 플래그를 단다.
    import json

    dest = materialize_release(tmp_path / "legacy")
    terms_path = dest / "terms.json"
    terms = json.loads(terms_path.read_text(encoding="utf-8"))
    for t in terms:
        if t["term_id"] == 4:
            t.pop("pattern", None)
            t["surface"] = "들켰노"  # 리터럴로 컴파일될 표면형
    terms_path.write_text(json.dumps(terms, ensure_ascii=False), encoding="utf-8")

    eng = Engine.load(dest)
    matches = eng.check("그거 들켰노 ㅋㅋ")["matches"]
    pat = next(m for m in matches if m["term_id"] == 4)
    assert pat["matched_text"] == "들켰노"
    assert "pattern_fallback_literal" in pat["flags"]


# --- 자모 경계 필터 ----------------------------------------------------------
def test_jamo_seam_no_false_positive(engine: Engine) -> None:
    # '전주'(ㅈㅓㄴㅈㅜ)는 'ㄴㅈ' 이음새를 포함하지만 사전 키가 음절 경계에
    # 정렬되지 않으므로 매칭되지 않아야 한다(원조/안주 류 회귀 감시).
    assert engine.check("전주 비빔밥 맛집")["matches"] == []
    # '안주'도 무해.
    assert engine.check("안주를 먹었다")["matches"] == []


def test_jamo_separated_input_matches(engine: Engine) -> None:
    # 사용자가 '운지'를 호환 자모로 풀어 써도 정규화로 수렴해 매칭된다.
    matches = engine.check("ㅇㅜㄴㅈㅣ ㅋㅋ")["matches"]
    assert any(m["surface"] == "운지" for m in matches)


# --- 변형(verified) 0.9 ------------------------------------------------------
def test_verified_variant_confidence_0_9(engine: Engine) -> None:
    # 삼일1한(leet 변형)은 verified 변형 → confidence 0.9, surface는 대표 용어.
    m = _one(engine, "삼일1한 표기")
    assert m["surface"] == "삼일한"
    assert m["match_confidence"] == 0.9
    # risk = 5/5 * 0.9 * 1.0 = 0.9 ≥ 0.7, sev5 → 여전히 revise.
    assert m["risk_score"] == pytest.approx(0.9)
    assert m["usage_recommendation"] == "revise_recommended"


# --- 원문 오프셋 정확성 ------------------------------------------------------
def test_offset_accuracy_with_spaces_and_symbols(engine: Engine) -> None:
    # 공백·특수문자가 앞에 섞여도 span이 원문 좌표를 정확히 가리킨다.
    text = "  ※경고※  삼일한!!!"
    m = _one(engine, text)
    s, e = m["span"]["start"], m["span"]["end"]
    assert text[s:e] == "삼일한"
    assert m["matched_text"] == "삼일한"


def test_offset_accuracy_multiple_matches(engine: Engine) -> None:
    text = "운지 그리고 삼일한"
    matches = engine.check(text)["matches"]
    for m in matches:
        s, e = m["span"]["start"], m["span"]["end"]
        # surface가 패턴이 아니면 원문 슬라이스가 matched_text와 일치.
        assert text[s:e] == m["matched_text"]
    # 시작 오프셋 오름차순 정렬.
    starts = [m["span"]["start"] for m in matches]
    assert starts == sorted(starts)


# --- 단계 on/off + 디버그 타이밍 --------------------------------------------
def test_stage_toggle_morpheme_off_reintroduces_match(engine: Engine) -> None:
    # 형태소 경계 단계를 끄면 '운지버섯' 안의 '운지'가 다시 후보가 된다
    # (safe_context도 함께 꺼야 매치가 남음 — '버섯'이 창 안에 있으므로).
    on = engine.check("운지버섯을 채취했다")
    off = engine.check(
        "운지버섯을 채취했다",
        stages={"morpheme_boundary": False, "safe_context": False},
    )
    assert on["matches"] == []
    assert any(m["surface"] == "운지" for m in off["matches"])


def test_debug_stage_timings_present(engine: Engine) -> None:
    debug = engine.check("삼일한 테스트")["debug"]
    assert "stage_timings_ms" in debug
    assert "normalize" in debug["stage_timings_ms"]
    assert "scoring" in debug["stage_timings_ms"]


def test_no_match_returns_none(engine: Engine) -> None:
    r = engine.check("오늘 날씨가 참 좋습니다")
    assert r["matches"] == []
    assert r["overall_recommendation"] == "none"


# --- 성능 (1,000자 × 100회 p95) ---------------------------------------------
def test_p95_latency_under_guard(engine: Engine) -> None:
    # 1,000자 입력 100회의 p95를 측정. 느린 CI 대비 assert 가드는 500ms,
    # 측정값은 출력해 회귀를 눈으로 추적한다(목표 p95 < 150ms).
    text = ("운지버섯과 한남동 부동산, 그리고 503 코드에 대한 마케팅 카피 문장입니다. ") * 14
    text = text[:1000]
    engine.check(text)  # 워밍업(Kiwi 콜드스타트 제외)
    durations = []
    for _ in range(100):
        t0 = time.perf_counter()
        engine.check(text)
        durations.append((time.perf_counter() - t0) * 1000.0)
    durations.sort()
    p95 = durations[94]
    print(
        f"\n[perf] 1000자×100회 p95={p95:.1f}ms "
        f"median={durations[49]:.1f}ms max={durations[-1]:.1f}ms"
    )
    assert p95 < 500.0, f"p95={p95:.1f}ms (가드 500ms 초과)"
