"""검사 엔진 테스트 (M2-B) — docs/03 §2 파이프라인·정책표 v1.

fixtures/release_test 아티팩트(손작성)를 conftest의 engine 픽스처로 로드한다.
케이스 출처: 작업 명세 + docs/06 §1 골든셋 슬롯(운지버섯·원조/안주·한남동).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from noise_checker.engine import Engine, compiled_normalizer_version
from tests.conftest import materialize_release

_GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
# release_test 픽스처에 적재된 surface (must_pass 회귀 채점 대상 필터).
_FIXTURE_SURFACES = {"운지", "삼일한", "한남", "된장녀", "노무", "503", "~노", "탱크데이"}


def _fixture_must_pass_rows() -> list[dict]:
    """must_pass 중 픽스처에 적재된 용어를 참조하는 행만(엔진이 평가 가능한 부분)."""
    rows = []
    for line in (_GOLDEN_DIR / "must_pass.jsonl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        e = json.loads(line)
        if e.get("term_ref") in _FIXTURE_SURFACES and e.get("gate_status") is None:
            rows.append(e)
    return rows


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


# --- 변형(chosung) 캡 0.7 + 상한 review ------------------------------------
def test_chosung_variant_capped_to_review(engine: Engine) -> None:
    # 'ㅅㅇㅎ'(삼일한 chosung 변형, sev5 unambiguous)도 chosung은 본질 lossy →
    # confidence 0.7 + 상한 review(revise 금지) + flag 'chosung_variant'.
    m = _one(engine, "ㅅㅇㅎ 하자")
    assert m["surface"] == "삼일한"
    assert m["match_confidence"] == 0.7
    assert "chosung_variant" in m["flags"]
    # risk = 5/5 * 0.7 * 1.0 = 0.7 ≥ 0.7, sev5 → 캡 없으면 revise였을 것이나 상한 review.
    assert m["risk_score"] == pytest.approx(0.7)
    assert m["usage_recommendation"] == "review_recommended"


def test_chosung_variant_never_revise_invariant(engine: Engine) -> None:
    # chosung 변형 매치는 어떤 경우에도 revise가 아니다(단독 매칭 위험 잔존 불변식).
    for m in engine.check("ㅅㅇㅎ")["matches"]:
        if "chosung_variant" in m["flags"]:
            assert m["usage_recommendation"] != "revise_recommended"


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


# === M2 2차 핫픽스 ① — 인용·메타담론 휴리스틱 (F19/F20) =====================
def test_quotation_quote_wrapped_severe_capped_to_review(engine: Engine) -> None:
    # 따옴표로 감싼 severity 5 unambiguous(삼일한)도 인용 → 상한 review(revise 금지).
    m = _one(engine, "'삼일한' 같은 폭력 선동 표현은 규탄받아야 한다")
    assert m["surface"] == "삼일한"
    assert m["usage_recommendation"] == "review_recommended"
    assert "quotation_heuristic" in m["flags"]


def test_quotation_metadiscourse_token_caps_severe(engine: Engine) -> None:
    # ±15자 창에 메타담론 토큰('혐오 표현')이 있으면 인용으로 보고 상한 review.
    m = _one(engine, "삼일한 같은 혐오 표현이 담론에 미친 영향을 다룬 보고서")
    assert m["surface"] == "삼일한"
    assert m["usage_recommendation"] == "review_recommended"
    assert "quotation_heuristic" in m["flags"]


def test_quotation_plain_usage_still_revise(engine: Engine) -> None:
    # 인용 신호 없는 평문 사용은 그대로 revise (happy-path 미차단).
    m = _one(engine, "그는 삼일한 하자고 선동했다")
    assert m["usage_recommendation"] == "revise_recommended"
    assert "quotation_heuristic" not in m["flags"]


def test_quotation_moyok_token_excluded(engine: Engine) -> None:
    # '모욕'은 메타담론 토큰에서 제외 — 혐오 행위 서술이 인용으로 강등되지 않는다.
    m = _one(engine, "삼일한 같은 말로 모욕하는 게시물")
    assert m["usage_recommendation"] == "revise_recommended"
    assert "quotation_heuristic" not in m["flags"]


def test_quotation_match_not_removed_only_capped(engine: Engine) -> None:
    # 인용이어도 매치는 제거되지 않는다(자문 포지셔닝 — 검토 가치 유지).
    matches = engine.check("'삼일한'이라는 표현을 분석한 논문")["matches"]
    assert len(matches) == 1
    assert matches[0]["surface"] == "삼일한"


def test_quotation_stage_toggle_off_restores_revise(engine: Engine) -> None:
    # quotation 단계를 끄면 상한이 사라져 다시 revise가 된다(단계 on/off 검증).
    r = engine.check("'삼일한' 같은 폭력 선동 표현", stages={"quotation": False})
    m = next(x for x in r["matches"] if x["surface"] == "삼일한")
    assert m["usage_recommendation"] == "revise_recommended"
    assert "quotation_heuristic" not in m["flags"]


# === M2 2차 핫픽스 ② — skip-char 창 스캔 ====================================
def test_skipchar_dot_insert_matches(engine: Engine) -> None:
    # '노.무' — 음절 사이 마침표 1개 제거 뷰에서 복원, confidence 0.8.
    m = _one(engine, "노.무")
    assert m["surface"] == "노무"
    assert m["match_confidence"] == 0.8
    assert "skip_char" in m["flags"]
    # 원문 span은 결합 구간 전체(노.무)를 가리킨다.
    assert m["span"] == {"start": 0, "end": 3}


def test_skipchar_line_break_matches(engine: Engine) -> None:
    # '한\n남' — 줄바꿈 1개 삽입도 복원.
    m = _one(engine, "한\n남")
    assert m["surface"] == "한남"
    assert "skip_char" in m["flags"]


def test_skipchar_multi_separator_matches(engine: Engine) -> None:
    # '된.장.녀' — 음절마다 구분자 삽입(각 1개)도 전부 복원.
    m = _one(engine, "된.장.녀")
    assert m["surface"] == "된장녀"
    assert m["match_confidence"] == 0.8


def test_skipchar_space_split_capped_to_review(engine: Engine) -> None:
    # '삼 일 한' — 공백 결합 매치는 ambiguity 무관 상한 review (revise 금지 불변식).
    m = _one(engine, "삼 일 한")
    assert m["surface"] == "삼일한"
    assert "skip_char" in m["flags"]
    assert m["usage_recommendation"] == "review_recommended"  # revise 아님


def test_skipchar_space_split_never_revise_invariant(engine: Engine) -> None:
    # 공백 결합 skip-char 매치는 어떤 경우에도 revise가 아니다(불변식).
    for text in ("삼 일 한", "한 남"):
        for m in engine.check(text)["matches"]:
            if "skip_char" in m["flags"]:
                assert m["usage_recommendation"] != "revise_recommended"


def test_skipchar_normal_sentence_no_false_positive(engine: Engine) -> None:
    # '좌측 좀비 떼' 같은 일반 문장은 skip-char 결합으로 오탐되지 않는다
    # (음절 사이가 단일 구분자로 직접 이어지지 않음).
    assert engine.check("좌측 좀비 떼가 다가온다")["matches"] == []


def test_skipchar_no_duplicate_with_exact(engine: Engine) -> None:
    # 구분자 없는 정상 입력은 exact만 — skip-char 중복 매치가 생기지 않는다.
    matches = engine.check("삼일한 하자")["matches"]
    assert len(matches) == 1
    assert "skip_char" not in matches[0]["flags"]


def test_skipchar_stage_toggle_off(engine: Engine) -> None:
    # skip_char 단계를 끄면 '노.무'는 복원되지 않는다.
    assert engine.check("노.무", stages={"skip_char": False})["matches"] == []


def test_skipchar_run_cap_three_separators_not_joined(engine: Engine) -> None:
    # 구분자 3연속은 결합하지 않는다(_SKIP_MAX_RUN=2 — 보수적 오탐 방지).
    assert engine.check("노...무")["matches"] == []


# === M2 2차 핫픽스 ③ — 형태소 경계 재검(기본 Kiwi) =========================
def test_boundary_recheck_drops_nomura(engine: Engine) -> None:
    # '본조 노무라 라멘' — 사용자 사전 '노무' 부스트가 '노무라'를 쪼개 경계 검사를
    # 통과시키지만, 기본 Kiwi 재검으로 '노무'가 '노무라' 토큰 내부임을 확인해 폐기.
    assert engine.check("본조 노무라 라멘으로 알려진 식당")["matches"] == []


def test_boundary_recheck_keeps_nomuhan(engine: Engine) -> None:
    # '노무한 박수' — 기본 Kiwi도 '노무'를 독립 토큰으로 분석 → 매치 유지(미탐 방지).
    m = _one(engine, "노무한 박수")
    assert m["surface"] == "노무"
    assert "boundary_recheck_dropped" not in m["flags"]


def test_boundary_recheck_keeps_josa_attached(engine: Engine) -> None:
    # '맘충이라고' 류 조사 결합 회귀 감시 — '된장녀라니'(명사+조사)는 살아남는다.
    # (기본 Kiwi가 '된장녀'를 NNP로 보존하고 '라니'를 조사/어미로 분석.)
    m = _one(engine, "저 된장녀라니 진짜")
    assert m["surface"] == "된장녀"
    assert "boundary_recheck_dropped" not in m["flags"]


def test_boundary_recheck_keeps_oov_derivative_with_review_cap(engine: Engine) -> None:
    # '응디시티' — 기본 Kiwi OOV 신조어 내부의 '응디' 매치는 폐기하지 않는다
    # (비하 파생어 미탐 방지). 경계 불확실 → 상한 review로 보수 처리.
    m = _one(engine, "응디시티 드립으로 고인을 조롱하는 게시물")
    assert m["surface"] == "응디"
    assert "oov_boundary_kept" in m["flags"]
    assert m["usage_recommendation"] in ("review_recommended", "monitor")


def test_boundary_recheck_keeps_reduplicated_mockery(engine: Engine) -> None:
    # '된장녀된장녀' 식 중첩 조롱 — 기본 Kiwi가 OOV 한 토큰으로 묶어도 매치 유지.
    r = engine.check("된장녀된장녀 거리는 글")
    assert any(m["surface"] == "된장녀" for m in r["matches"])


def test_boundary_recheck_only_when_adjacent_hangul(engine: Engine) -> None:
    # 직전/직후가 한글이 아니면(공백·문장부호) 재검을 트리거하지 않아 정상 매치 유지.
    m = _one(engine, "그 노무 표기")
    assert m["surface"] == "노무"


def test_boundary_recheck_drops_when_edge_cuts_base_token(engine: Engine) -> None:
    # '삼일한약방'(F8 동음이의어): 부스트가 '삼일한'을 분리하지만 기본 Kiwi는 끝
    # 경계가 '한약방' 토큰 내부를 가로지름 → 폐기(전체 토큰 포함이 아닌 경계 절단도 처리).
    assert engine.check("삼일절 끝나고 삼일한약방 앞에서 만났다")["matches"] == []


# === 골든셋 must_pass 회귀 (픽스처 엔진 채점 — 핫픽스 ①③ + skip-char 오탐 감시) ===
@pytest.mark.parametrize(
    "row",
    _fixture_must_pass_rows(),
    ids=lambda r: f"{r['slot']}-{r['term_ref']}-{r['grade']}",
)
def test_must_pass_fixture_terms_no_overflag(engine: Engine, row: dict) -> None:
    """픽스처 용어를 참조하는 must_pass 행을 러너와 동일 규칙으로 채점한다.

    grade=ambiguous → revise가 있으면 실패(인용 휴리스틱이 막아야 함, F18~F20).
    grade=strict|marketing → 어떤 매칭이든 있으면 실패(safe_context/형태소/skip-char
    경계가 막아야 함). 새 경로(skip-char·경계 재검·인용 상한)의 오탐을 감시한다.
    """
    matches = engine.check(row["text"])["matches"]
    if row["grade"] == "ambiguous":
        revise = [m for m in matches if m["usage_recommendation"] == "revise_recommended"]
        assert not revise, f"인용/메타 맥락에서 revise 과잉 권고: {row['text']!r} -> {revise}"
    else:  # strict | marketing
        assert not matches, f"무해 입력에 매칭 발생: {row['text']!r} -> {matches}"


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
