# 07. 서브 에이전트 구성 — 역할, 스킬, 기술 스택

각 에이전트는 `.claude/agents/*.md`에 Claude Code 서브에이전트로 정의되어 있어
이 저장소에서 `@agent-name`으로 즉시 호출할 수 있다. 정의 파일에 상세 작업 규칙이 있고, 여기서는 전체 그림을 요약한다.

## 1. 에이전트 맵 (데이터 흐름 순)

```
[lexicon-researcher] ──후보 엔트리──▶ [data-curator] ──정제 데이터──▶ Lexicon DB
        ▲                                  ▲                          │
        │ 신조어 후보 피드백                  │ 공개 데이터셋                │
        │                                  │                          ▼
[pipeline-engineer] ◀──수집 스케줄──────────┘                  [variant-engineer]
        │                                                            │ 변형 보강
        │ 릴리스 아티팩트                                               ▼
        └────────▶ [detection-engineer] ◀──문맥분류 모델── [ml-engineer]
                          │
                   [image-engineer]
                          │
                          ▼
                   [qa-redteam] ──회귀/레드팀 결과──▶ 전 에이전트 피드백
```

## 2. 역할 × 스킬 × 기술 스택 매트릭스

| 에이전트 | 핵심 책임 | 필수 스킬 | 기술 스택 | 주요 산출물 |
|---|---|---|---|---|
| **lexicon-researcher** | 신규 용어/표식 웹 조사, 출처·유래 확보 | 커뮤니티 지형 이해, 출처 신뢰도 평가, 교차 검색 | WebSearch/WebFetch, archive.org | `data/candidates/*.json` |
| **data-curator** | 데이터셋 통합, 라벨 매핑, 중복 제거, 라이선스 분류 | 라이선스 판독, 스키마 정합성 | pandas, HF datasets, jsonschema | `data/seed/*.json`, ETL 로더 |
| **variant-engineer** | 변형 자동 생성·검증, 회피 사례 보강 | 한글 유니코드, 변형 패턴 분석 | regex, hypothesis, 자모 처리 | `src/variants/rules.py`, evasion 후보(→`tests/golden/evasion.jsonl` 머지) |
| **detection-engineer** | 텍스트 검사 파이프라인 + API | 고성능 문자열 매칭, 오프셋 매핑 | FastAPI, pyahocorasick, kiwipiepy | 검사 API, `src/normalizer.py` |
| **ml-engineer** | 문맥 분류기 학습·서빙, LLM 폴백 | 파인튜닝, 평가 설계, calibration | transformers, KcELECTRA, ONNX, Claude API | 분류 모델 + 모델 카드 |
| **image-engineer** | 이미지 검사 3갈래 파이프라인 | OCR/해시/임베딩/랜드마크 | PaddleOCR, imagehash, OpenCLIP, MediaPipe, Redis 큐 | 이미지 워커 |
| **pipeline-engineer** | 수집 스케줄러, 사전 빌드·릴리스, 검수 콘솔(MVP Streamlit→확장 시 Next.js) | **합법 소스 화이트리스트 수집** (커뮤니티 직접 크롤링·나무위키 자동수집 전면 금지), 증분 수집, 릴리스 게이트 | APScheduler→Airflow, 위키/뉴스 API, Alembic | 수집기, 릴리스 빌더, 검수 콘솔 |
| **qa-redteam** | 골든셋, FP/FN 평가, 레드팀, 부하 테스트 | 적대적 사고, 평가 지표 설계 | pytest, hypothesis, locust | `tests/golden/*`, 평가 리포트 |

## 3. 협업 프로토콜

- **인터페이스 우선**: 에이전트 간 주고받는 데이터는 전부 `data/` 하위 JSON 스키마로 고정 (`docs/02-database-design.md` 기준). 스키마 변경은 data-curator가 소유.
- **단일 정규화 소스**: `src/normalizer.py`는 detection-engineer가 소유하고 전원이 import — 재구현 금지.
- **품질 게이트**: qa-redteam의 골든셋 회귀를 통과하지 못하면 어떤 에이전트의 변경도 릴리스 불가.
- **피드백 루프**: 검사 API의 `out_of_lexicon_warning`(사전 외 고위험 문장)과 `/v1/feedback`(오탐/미탐 신고)은 lexicon-researcher의 다음 조사 큐가 된다.
- **사람 검수 불변 원칙**: 어떤 에이전트도 용어를 직접 `active`로 전이할 수 없다 — 후보 생성과 근거 첨부까지만.

## 4. 호출 예시 (이 저장소에서)

```
# 신규 논란 용어 조사
@lexicon-researcher 최근 3개월 내 기업 마케팅에서 논란이 된 커뮤니티 용어를 조사해 후보 엔트리로 만들어줘

# 데이터셋 적재
@data-curator UnSmile 데이터셋을 받아 카테고리 매핑 후 data/corpus/에 적재해줘

# 회피 테스트
@qa-redteam 현재 사전 기준으로 자모분리+특수문자 혼합 회피 케이스 50개를 만들어 evasion 셋을 보강해줘
```
