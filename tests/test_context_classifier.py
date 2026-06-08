"""문맥 분류기 테스트 (M3) — 결정성·동음이의 분리·미탑재 폴백·엔진 통합.

models/context_clf.json(학습 산출)이 존재하면 분류기 품질을, 없으면(미학습 환경)
구조·폴백만 검증한다. 엔진 통합은 conftest의 release_test 픽스처에 분류기를
주입해 ambiguous 매치 등급 변화를 본다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from noise_checker.context_classifier import (
    FEATURE_VERSION,
    ContextClassifier,
    extract_features,
)
from noise_checker.engine import Engine
from tests.conftest import materialize_release

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "context_clf.json"
_HAS_MODEL = MODEL_PATH.exists()
_requires_model = pytest.mark.skipif(not _HAS_MODEL, reason="학습된 모델 없음(미학습 환경)")


# --- 피처 결정성 ------------------------------------------------------------
def test_extract_features_deterministic() -> None:
    a = extract_features("저 한남 진짜 별로", "한남")
    b = extract_features("저 한남 진짜 별로", "한남")
    assert a == b
    assert all(isinstance(k, int) and isinstance(v, float) for k, v in a.items())


def test_extract_features_surface_changes_signal() -> None:
    # 동일 문장이라도 surface가 다르면 surface 네임스페이스 피처가 달라진다.
    f1 = extract_features("운지 ㅋㅋ", "운지")
    f2 = extract_features("운지 ㅋㅋ", "한남")
    assert f1 != f2


# --- 미탑재 폴백 (엔진) -----------------------------------------------------
def test_engine_without_classifier_falls_back_to_half(engine: Engine) -> None:
    # 분류기 미탑재 엔진(conftest)은 ambiguous context_score=0.5 폴백.
    m = engine.check("운지 ㅋㅋ")["matches"][0]
    assert m["surface"] == "운지"
    assert m["context_score"] == 0.5


def test_load_rejects_feature_version_mismatch(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"feature_version": "WRONG", "bias": 0.0, "weights": {}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="피처 버전 불일치"):
        ContextClassifier.load(bad)


def test_engine_load_rejects_missing_context_model(release_dir: Path) -> None:
    with pytest.raises(ValueError, match="문맥 분류기 경로"):
        Engine.load(release_dir, context_model=release_dir / "nonexistent.json")


# --- 분류기 품질 (모델 존재 시) ---------------------------------------------
@_requires_model
def test_score_is_deterministic() -> None:
    clf = ContextClassifier.load(MODEL_PATH)
    s1 = clf.score("운지 ㅋㅋ 꼬숩다", "운지")
    s2 = clf.score("운지 ㅋㅋ 꼬숩다", "운지")
    assert s1 == s2
    assert 0.0 <= s1 <= 1.0


@_requires_model
def test_feature_version_matches_code() -> None:
    data = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    assert data["feature_version"] == FEATURE_VERSION


@_requires_model
def test_homonym_benign_low_harmful_high() -> None:
    clf = ContextClassifier.load(MODEL_PATH)
    benign = [
        ("운지버섯은 면역에 좋다고 알려져 차로 끓여 마신다.", "운지"),
        ("어머니가 직접 담근 된장으로 끓인 된장찌개가 일품이다.", "된장녀"),
        ("주말에 한남동 카페 거리에 다녀왔다.", "한남"),
        ("흑산도 삭힌 홍어삼합에 막걸리 한잔이 최고다.", "홍어"),
    ]
    harmful = [
        ("명품백 들고 다니는 된장녀들 진짜 한심하다", "된장녀"),
        ("저 한남 진짜 역겹다 한남들은 다 똑같아", "한남"),
        ("또 운지 드립 치는 애 나타났네 진짜 인간성 어디 갔냐", "운지"),
    ]
    for t, s in benign:
        assert clf.score(t, s) < 0.5, f"benign이 0.5 이상: {s} | {t}"
    for t, s in harmful:
        assert clf.score(t, s) > 0.5, f"harmful이 0.5 이하: {s} | {t}"


@_requires_model
def test_counterspeech_and_quotation_score_low() -> None:
    # 대항표현·메타 인용은 harmful이 아니다(저score).
    clf = ContextClassifier.load(MODEL_PATH)
    assert clf.score("'한남'이라며 남성 전체를 싸잡는 혐오 표현은 차별이다.", "한남") < 0.5
    assert clf.score("기사는 '운지'가 고인 조롱 은어로 자리 잡은 경위를 설명했다.", "운지") < 0.5


# --- 엔진 통합 (분류기 주입) ------------------------------------------------
def _engine_with_clf(tmp_path: Path) -> Engine:
    dest = materialize_release(tmp_path / "rel")
    return Engine.load(dest, context_model=MODEL_PATH)


@_requires_model
def test_engine_ambiguous_benign_context_score_drops_and_downgrades(tmp_path: Path) -> None:
    # ambiguous benign 문장(safe_context 미해당이지만 무해 어조): 분류기 context_score가
    # 0.5보다 낮아져 risk가 하락 → review 상한이 monitor로 등급 하향(해소 효과).
    # M3 전(0.5 고정)이면 risk=4/5*1.0*0.5=0.4 ≥ 0.35 → review였을 케이스.
    eng = _engine_with_clf(tmp_path)
    res = eng.check("운지라는 친구를 오늘 만났어")
    un = [m for m in res["matches"] if m["surface"] == "운지"]
    assert un, "운지 매치가 있어야 한다(safe_context 미해당)"
    assert un[0]["context_score"] < 0.5
    assert un[0]["usage_recommendation"] == "monitor"


@_requires_model
def test_engine_ambiguous_harmful_high_score_keeps_review(tmp_path: Path) -> None:
    # ambiguous harmful 고score 문장: context_score가 0.5보다 크게 올라간다(정상 등급).
    eng = _engine_with_clf(tmp_path)
    res = eng.check("저 한남 진짜 역겹다 한남들은 다 똑같아")
    hn = [m for m in res["matches"] if m["surface"] == "한남"]
    assert hn, "한남 매치가 있어야 한다"
    assert hn[0]["context_score"] > 0.5
    assert hn[0]["usage_recommendation"] == "review_recommended"


@_requires_model
def test_engine_low_confidence_flag_matches_score_range(tmp_path: Path) -> None:
    # LLM 폴백 훅: context_score가 경계 구간(0.4~0.6)일 때만 flag가 달린다.
    eng = _engine_with_clf(tmp_path)
    res = eng.check("한남 친구랑 같이 점심 먹었어")
    hn = [m for m in res["matches"] if m["surface"] == "한남"]
    assert hn, "한남 매치가 있어야 한다"
    cs = hn[0]["context_score"]
    in_range = 0.4 <= cs <= 0.6
    assert ("context_low_confidence" in hn[0]["flags"]) == in_range
