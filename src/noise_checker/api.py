"""검사 API (M2-B) — FastAPI `/v1/check/text`.

docs/03-architecture.md §4(API 설계)·§6(법적 포지셔닝)을 따른다.

- 엔진은 NOISE_RELEASE_DIR 환경변수의 아티팩트를 앱 lifespan에서 1회 로드.
- 응답은 engine.check 결과 + **자문형 권고 문구**(판정 아님 — "수정 검토를
  권고합니다" 톤)와 강제 고지(usage_notice)를 덧붙인다.
- 유래(origin) 텍스트는 응답에 포함하지 않는다 (SA 비노출 기본값 — terms.json에
  애초 없음). 이 API는 매칭·권고만 노출한다.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from noise_checker.engine import Engine

# 모든 응답에 강제 포함하는 2차 피해 방지 고지 (03 §4/§6 — 생략 불가 필드).
USAGE_NOTICE = (
    "본 결과는 리스크 자문 의견이며 사실 판정이 아닙니다. "
    "특정인에 대한 의도 추정·인사 조치의 근거로 사용하지 마십시오. "
    "최종 판단과 책임은 이용 고객에게 있습니다."
)

# usage_recommendation → 자문형 권고 문구 (자문형 동사만, 단정형 금지 — 03 §4).
_ADVISORY_TEXT = {
    "revise_recommended": "표현 수정 검토를 권고합니다.",
    "review_recommended": "내부 검토를 권고합니다.",
    "monitor": "참고·관찰을 권고합니다.",
    "none": "권고 사항이 없습니다.",
}


class CheckTextRequest(BaseModel):
    text: str = Field(..., description="검사할 원문 텍스트")


def _advisory(recommendation: str) -> str:
    return _ADVISORY_TEXT.get(recommendation, _ADVISORY_TEXT["monitor"])


def build_response(result: dict[str, Any]) -> dict[str, Any]:
    """engine.check 결과에 자문형 문구·고지를 덧붙여 API 응답을 조립한다."""
    matches = []
    for m in result["matches"]:
        item = dict(m)
        item["advisory"] = _advisory(m["usage_recommendation"])
        matches.append(item)
    return {
        "release_version": result["release_version"],
        "overall_recommendation": result["overall_recommendation"],
        "overall_advisory": _advisory(result["overall_recommendation"]),
        "usage_notice": USAGE_NOTICE,
        "matches": matches,
        "debug": result.get("debug", {}),
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """앱 기동 시 NOISE_RELEASE_DIR 아티팩트를 1회 로드해 엔진을 보관한다."""
    release_dir = os.environ.get("NOISE_RELEASE_DIR")
    if not release_dir:
        raise RuntimeError("NOISE_RELEASE_DIR 환경변수가 필요합니다 (릴리스 아티팩트 경로).")
    app.state.engine = Engine.load(Path(release_dir))
    yield
    app.state.engine = None


app = FastAPI(title="Noise Checker — Detection API", version="v1", lifespan=lifespan)


@app.post("/v1/check/text")
def check_text(req: CheckTextRequest) -> dict[str, Any]:
    """텍스트를 검사해 매칭·권고·고지를 반환한다 (동기)."""
    engine: Engine | None = getattr(app.state, "engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="검사 엔진이 로드되지 않았습니다.")
    result = engine.check(req.text)
    return build_response(result)
