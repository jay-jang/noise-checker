"""FastAPI `/v1/check/text` 계약 테스트 (M2-B).

NOISE_RELEASE_DIR에 release_test 아티팩트를 머티리얼라이즈한 뒤 앱 lifespan으로
엔진을 로드한다. 응답 스키마·자문형 문구·고지(usage_notice)·SA 비노출을 검증.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import materialize_release


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    release = materialize_release(tmp_path / "release")
    monkeypatch.setenv("NOISE_RELEASE_DIR", str(release))
    # 환경변수 설정 후 app을 import해야 lifespan이 그 경로를 읽는다.
    from noise_checker.api import app

    with TestClient(app) as c:
        yield c


def test_check_text_schema(client: TestClient) -> None:
    resp = client.post("/v1/check/text", json={"text": "삼일한 하자"})
    assert resp.status_code == 200
    body = resp.json()
    # 최상위 필수 필드.
    assert body["release_version"] == "2026.06.05-1"
    assert body["overall_recommendation"] == "revise_recommended"
    assert "usage_notice" in body and body["usage_notice"]
    assert "overall_advisory" in body
    # 매치 항목 스키마.
    m = body["matches"][0]
    for key in (
        "span",
        "matched_text",
        "surface",
        "term_id",
        "categories",
        "severity",
        "ambiguity",
        "match_confidence",
        "context_score",
        "risk_score",
        "usage_recommendation",
        "flags",
        "advisory",
    ):
        assert key in m, f"매치 필드 누락: {key}"
    assert m["span"]["start"] == 0 and m["span"]["end"] == 3


def test_advisory_wording_is_non_adjudicative(client: TestClient) -> None:
    # 자문형 문구 — 단정형('~입니다'로 끝나는 판정)·금지 동사를 쓰지 않는다.
    resp = client.post("/v1/check/text", json={"text": "삼일한"})
    body = resp.json()
    advisory = body["matches"][0]["advisory"]
    assert "권고" in advisory
    for banned in ("제거하세요", "차단", "일베 표현"):
        assert banned not in advisory


def test_no_origin_text_in_response(client: TestClient) -> None:
    # SA 비노출 기본값 — 유래(origin/summary) 텍스트는 응답에 없다.
    resp = client.post("/v1/check/text", json={"text": "운지 ㅋㅋ"})
    body = resp.json()
    assert "origin" not in body["matches"][0]
    assert "summary" not in body["matches"][0]


def test_clean_text_returns_none(client: TestClient) -> None:
    resp = client.post("/v1/check/text", json={"text": "오늘 점심 메뉴 추천"})
    body = resp.json()
    assert body["overall_recommendation"] == "none"
    assert body["matches"] == []
    assert body["usage_notice"]  # 매치가 없어도 고지는 강제 포함.


def test_missing_text_is_422(client: TestClient) -> None:
    resp = client.post("/v1/check/text", json={})
    assert resp.status_code == 422


def test_safe_context_resolution_through_api(client: TestClient) -> None:
    resp = client.post("/v1/check/text", json={"text": "운지버섯을 채취했다"})
    body = resp.json()
    assert body["matches"] == []
    assert body["overall_recommendation"] == "none"
