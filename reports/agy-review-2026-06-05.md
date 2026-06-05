# Antigravity(agy) 독립 방향성 리뷰 — 2026-06-05

> 도구: Antigravity CLI 1.0.5 (Gemini) / 입력: 동일 문서 직접 읽기

# Noise Checker 프로젝트 시니어 아키텍트 비판적 리뷰 보고서

- **작성 일자:** 2026-06-05
- **작성자:** Antigravity (시니어 아키텍트)
- **대상 프로젝트:** Noise Checker (한국어 혐오 용어/표식 검출 서비스)

본 보고서는 Noise Checker 프로젝트의 아키텍처, 데이터 전략, 구현 계획 및 이전 적대적 리뷰 반영 현황을 시니어 아키텍트의 관점에서 비판적으로 검토한 독립 리뷰 결과입니다.

---

## Part 1. 이전 적대적 리뷰(review-2026-06-04.md) 반영 교차 검증 결과

이전 적대적 리뷰에서 지적된 18가지 이슈(Critical 4건, Major 13건, Minor 1건)에 대해 프로젝트 문서 및 에이전트 규칙을 교차 검증한 결과, **18건 모두 설계와 프로필 수준에서 누락 없이 매우 일관되게 반영되었음**을 확인했습니다.

*   **크롤링 정책 일관성 (이슈 1):** `.claude/agents/pipeline-engineer.md` 규칙 5와 `docs/04-update-pipeline.md` 원칙 2/§7에 커뮤니티 직접 크롤링과 나무위키 자동 수집 금지가 화이트리스트 기반의 코드 레벨 차단 설계와 함께 완벽히 정합되어 있습니다.
*   **라이선스 전파 모델 (이슈 2, 3, 5):** `docs/02-database-design.md`에 `license_class` 및 `effective_license` 필드가 설계되었고, `docs/04-update-pipeline.md` 빌드 게이트 0에서 라이선스 불명(`unknown`/`restricted`) 자원의 유출 차단이 명시되었습니다. `attribution.json` 생성 기능이 아티팩트 빌드 구성에 완벽히 연동되었습니다.
*   **공연성 차단 거버넌스 (이슈 4):** `incident` 테이블에 `disclosable`, `legal_reviewed`, `display_title` 필드가 추가되었으며, API 응답(`GET /v1/lexicon/terms/{id}`) 시 기업 실명과 `sample_text`가 절대로 노출되지 않도록 데이터 접근을 일관되게 제어하고 있습니다.
*   **오프셋 및 자모 매칭 예외 처리 (이슈 7, 8):** `docs/02-database-design.md` §4.1에 `src_offset` 불변식 및 음절 경계 스냅 규칙이 수립되었고, `docs/03-architecture.md` 단계 1에서 이음새 부분 매치 오탐 필터가 명시되었으며, `docs/06-test-plan.md` 회귀 슬롯으로 모니터링되도록 완벽히 통합되었습니다.
*   **의존성 역전 해결 (이슈 16):** M2 단계에서 M3 문맥 분류기에 의존하지 않도록 `must_pass`의 ambiguous 항목 채점을 "block 발생만 실패로 카운트"하는 등급별 규칙이 `docs/06-test-plan.md` §1, `docs/05-implementation-plan.md` M2 출시 기준, `docs/04-update-pipeline.md` 게이트 2에 유기적으로 연동되었습니다.

---

## Part 2. 심각도별 추가 발견 사항 및 개선 제안

이전 리뷰가 완벽히 반영되었음에도 불구하고, 실제 프로덕션 서빙, 한국어 자연어 처리(NLP) 특성, 그리고 데이터 수집의 한계로 인해 발생하는 **신규 기술적 공백 및 위험 요인 10건**을 발견하여 아래와 같이 보고합니다. (칭찬은 생략하고 문제점 중심으로 서술합니다.)

### 1. Critical (심각)

#### 발견 1. 한국어 NLP 형태소 분석기(Kiwi) 의존성 및 신조어/변형문 미탐 한계
*   **근거:** [03-architecture.md:L40-42](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L40-L42), [03-architecture.md:L45-47](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L45-L47)
*   **문제점:** 텍스트 검사 파이프라인은 입력 문장당 1회 Kiwi 형태소 분석을 수행하여 조사/어미 부착 여부와 음절 경계를 확인하도록 설계되었습니다. 그러나 악성 신조어, 특수 문자 삽입 변형, 자모 분리 상태의 입력은 표준 형태소 분석기가 올바르게 토큰화하지 못하고 미등록 단어(OOV) 오류를 낼 확률이 높습니다. Kiwi가 형태소 분석에 실패하여 엉뚱한 경계로 단어를 분할할 경우, 이후 단계의 '음절 경계 정렬 필터'나 `safe_contexts` 대조 필터가 무력화되어 심각한 미탐 또는 오탐을 유발하게 됩니다.
*   **개선 제안:** 
    1. 1차 Aho-Corasick 매칭 단계에서는 형태소 경계 정보에 의존하지 않는 정규화된 자모 기반의 윈도우 매칭(Char/Jamo-level sliding window)을 우선 적용해야 합니다.
    2. 형태소 분석기(Kiwi) 결과는 '오탐 제거를 위한 보조적 필터(예: 조사가 확실히 붙었는지 검사)' 용도로만 제한적으로 활용해야 합니다.
    3. 사전 빌드 단계에서 `active` 상태로 승인된 사전에 등록된 모든 용어를 Kiwi의 사용자 사전(User Dictionary)에 동적으로 추가하여 빌드하는 자동화 흐름을 릴리스 파이프라인에 의무화하십시오.

#### 발견 2. 남성혐오(Misandry) lexicon의 극심한 데이터 편향 및 수집 기아(Starvation) 리스크
*   **근거:** [01-research-report.md:L8-10](file:///home/ubuntu/workspace/noise-checker/docs/01-research-report.md#L8-L10), [05-implementation-plan.md:L33-35](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L33-L35)
*   **문제점:** 남성혐오 표현이 마케팅 실사고의 다수를 차지함에도 불구하고 공개된 구조화 사전이나 데이터셋이 전무하여 페미위키(CC BY-SA 4.0)와 학술자료(박대아 2018)를 기반으로 직접 구축하도록 설정되었습니다. 그러나 페미위키는 서술의 젠더 편향성이 강해 이를 교차검증 없이 DB에 수용하면 주관적이거나 편향된 유래 설명이 유입되어 브랜드 세이프티의 핵심 가치인 '객관적 근거주의'가 훼손됩니다. 또한 박대아(2018) 등의 오래된 학술 데이터는 2024~2026년 최신 밈 및 도그휘슬을 포착하지 못하므로, 목표 건수(15+)를 채우더라도 실제 탐지 성능은 심각한 '데이터 기아'에 직면할 것입니다.
*   **개선 제안:** 
    1. 페미위키 등 편향 우려가 있는 위키 데이터를 정제하는 에이전트(`data-curator`) 프로세스에 "중립성 검수 가이드라인"을 공식 삽입하고, LLM 및 사람이 이를 교차 검증하는 규칙을 의무화해야 합니다.
    2. 최신 남성혐오 용어 포착을 위해 뉴스 보도 및 실제 커뮤니티 젠더 갈등 관련 소송 판례의 사실 관계를 역추적하는 경로를 M1 시드 구축의 필수 소스로 공식 지정하십시오.

---

### 2. Major (경고)

#### 발견 3. 문맥 분류기(KcELECTRA)의 학습 데이터 극소화로 인한 과적합(Overfitting) 위험
*   **근거:** [03-architecture.md:L56-60](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L56-L60), [05-implementation-plan.md:L47-49](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L47-L49)
*   **문제점:** 동음이의어 문맥 판단을 위해 "용어당 50쌍(총 100문장 내외)"의 대조 셋을 구축하여 KcELECTRA를 파인튜닝하는 계획은 딥러닝 모델의 크기에 비해 학습 데이터가 극도로 부족합니다. 이는 심각한 과적합(Overfitting)을 유발하여, 실제 프로덕션 환경의 다양한 문장 맥락에서 오작동할 위험이 큽니다.
*   **개선 제안:** 문맥 분류 초기 단계(M3)에는 무리한 딥러닝 파인튜닝 대신 LLM(Haiku 등)에 사전 정의된 `safe_contexts`와 유래 맥락을 프롬프트로 제공하여 Few-shot으로 판정하도록 아키텍처를 단순화해야 합니다. 이후 실제 유입되는 트래픽 및 피드백 데이터가 충분히 축적(예: 용어당 최소 500쌍 이상)된 시점부터 KcELECTRA ONNX 학습 모델로 점진적으로 전환하십시오.

#### 발견 4. 텍스트-이미지 검사 파이프라인의 동기/비동기 격리로 인한 B2B API 활용성 저하
*   **근거:** [03-architecture.md:L81-82](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L81-L82), [03-architecture.md:L87-90](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L87-L90)
*   **문제점:** 텍스트 검사는 동기 응답(<150ms/500ms), 이미지 검사는 비동기 응답(p95 10초)으로 분리되어 있습니다. 그러나 마케팅 카피나 카드뉴스의 특성상 이미지와 텍스트가 긴밀히 결합되어 배포되는데, B2B 고객사 시스템이 이 두 결과를 수집하기 위해 서로 다른 프로토콜(동기 API와 비동기 큐/웹훅)을 조합해 매칭하는 것은 클라이언트 측의 통합 처리를 비정상적으로 복잡하게 만듭니다.
*   **개선 제안:** 단일 캠페인이나 마케팅 자료 묶음을 한 번에 검사할 수 있는 통합 미디어 검사 API(`POST /v1/check/campaign`)를 추가 설계하고, 동기식 API에서도 이미지 검사가 완료될 때까지 블로킹 대기하는 옵션(`wait_for_image=true`)을 선택적으로 제공하여 클라이언트의 연동 편의성을 제고해야 합니다.

#### 발견 5. 라이선스 게이트의 과도한 차단으로 인한 실질적 사전 커버리지(Coverage) 붕괴
*   **근거:** [04-update-pipeline.md:L96-100](file:///home/ubuntu/workspace/noise-checker/docs/04-update-pipeline.md#L96-L100), [04-update-pipeline.md:L126-127](file:///home/ubuntu/workspace/noise-checker/docs/04-update-pipeline.md#L126-L127)
*   **문제점:** 라이선스 게이트 0에서 "noncommercial, restricted, unknown" 자원(UnSmile, 나무위키, KOLD 등)은 빌드 아티팩트에서 전면 제외합니다. 이로 인해 한국어 혐오표현의 가장 거대하고 풍부한 사전적 자원들을 사용할 수 없게 되어, 순수 CC BY-SA나 Permissive 라이선스만으로 구축된 사전은 극도로 협소해질 것이며 결과적으로 미탐율이 치명적으로 높아집니다.
*   **개선 제안:** 비상업적(NC)이나 불명 라이선스 소스는 "사전 데이터베이스에 직접 복제 등재"하는 것은 차단하되, 해당 소스를 통해 용어의 존재를 파악(단서 획득)한 후, 합법적인 뉴스 보도나 위키백과 등 청정 소스에서 재근거화하여 "완전히 재집필된 독자적 설명(original description)"을 작성하여 등재하는 우회 구축 프로세스(Clean Room Design)를 사전 편찬 매뉴얼에 공식화해야 합니다.

#### 발견 6. 마일스톤 순서상 '검수 콘솔'의 후순위 배치로 인한 M1 일정 지연 리스크
*   **근거:** [05-implementation-plan.md:L28-37](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L28-L37), [05-implementation-plan.md:L58-61](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L58-L61)
*   **문제점:** M1 단계는 300개 이상의 사전 항목과 유래, 출처를 검수하는 "임계경로(Critical Path)"이자 가장 손이 많이 가는 정교한 작업입니다. 그러나 수집기와 검수 콘솔(Streamlit)은 M5 단계에 개발되는 것으로 배치되어 있습니다. 즉, 가장 많은 양의 수동 검수가 필요한 M1 단계에서는 검수 도구가 없어 엑셀이나 로우 쿼리 등 비효율적인 수작업으로 검증을 진행해야 하므로 생산성 저하와 일정 지연이 불가피합니다.
*   **개선 제안:** 검수 콘솔 MVP(Streamlit 기반)의 개발 일정을 M0 혹은 M1의 초기 단계로 앞당겨 배치하여, 시드 사전을 구축할 때부터 검수자가 도구의 도움을 받아 효율적으로 작업할 수 있도록 해야 합니다.

#### 발견 7. 핫리로드 시 메모리 팽창 및 멀티 워커 환경에서의 동시성 OOM 리스크
*   **근거:** [03-architecture.md:L159-160](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L159-L160)
*   **문제점:** 무중단 사전 핫리로드를 위해 "이중 버퍼 로드 후 원자적 포인터 교체" 방식을 사용합니다. 하지만 Aho-Corasick 오토마톤, CLIP 이미지 인덱스, pgvector 커넥션 등 무거운 객체들을 메모리에 중복 로드할 때 순간적으로 메모리 사용량이 2배 이상 증가하여 컨테이너 환경에서 OOM(Out of Memory) crash가 발생할 위험이 있습니다. 특히 FastAPI가 멀티 워커 프로세스로 동작할 때 각 워커가 독립적으로 핫리로드를 수행하면 이 리스크가 배가됩니다.
*   **개선 제안:** 사전과 매칭 엔진을 FastAPI 애플리케이션의 내부 메모리에서 분리하여, 공유 메모리(Shared Memory)를 활용하거나 매칭 및 추론을 전담하는 경량 사이드카 프로세스(Rust 등)를 설계하여 메모리 사용량을 격리하고 버전 일관성을 확실히 해야 합니다.

#### 발견 8. 이미지 표식 검출의 극심한 오탐으로 인한 경고 피로(Alert Fatigue)
*   **근거:** [03-architecture.md:L85](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L85), [03-architecture.md:L153](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L153)
*   **문제점:** 집게손가락 등은 의도성 미입증 표식으로 분류되어 `warn` 경고를 띄웁니다. 그러나 일반적인 손동작(물건 잡기, 줌 등)에서도 메갈리아 집게손가락과 기하학적으로 유사한 패턴이 감지될 확률이 매우 높습니다. 무차별적인 `warn` 발생은 고객의 경고 피로를 유발해 시스템의 실효성을 낮춥니다.
*   **개선 제안:** 손동작 검출 시 1차 랜드마크 분석 후, 해당 부위의 이미지 영역을 잘라내어 주변 맥락(예: 캐릭터의 표정, 의상, 도구 소지 여부 등)을 파악하는 경량 비전 LLM(Vision-Language Model) 또는 멀티모달 모델을 통해 2차 필터링을 거친 후에만 최종 경고를 발생시키도록 보완해야 합니다.

---

### 3. Minor (일반)

#### 발견 9. 이전 리뷰 16번 반영(ambiguous 채점 규칙 예외)의 임시방편성으로 인한 실효성 저하
*   **근거:** [06-test-plan.md:L16-19](file:///home/ubuntu/workspace/noise-checker/docs/06-test-plan.md#L16-L19), [05-implementation-plan.md:L12](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L12)
*   **문제점:** M2 단계에서 문맥 분류기가 없으므로 ambiguous 항목에 대해 "block 발생만 실패로 카운트"하는 예외 규정을 두어 must_pass 98% 게이트를 통과시키고자 했습니다. 이는 빌드 게이트 통과를 위한 꼼수로, 실제 이 버전의 API를 사용하면 일반 동음이의어(예: 운지버섯)에 대해 모조리 `warn` 경고가 발생해 MVP 서비스의 신뢰성을 크게 훼손합니다.
*   **개선 제안:** M2 단계에서도 완전히 문맥 분류가 부재한 상태로 방치하지 말고, `docs/02-database-design.md`에 설계된 `safe_contexts` 필드를 이용해 하드코딩된 '부정 단어 필터링(예: 뒤에 "버섯", "법"이 붙으면 매칭 취소)' 로직을 M2의 필수 매칭 예외 규칙으로 강제 적용해야 합니다.

#### 발견 10. `source` 스키마 내의 `excerpt` 저작권 경계 모호성
*   **근거:** [02-database-design.md:L132](file:///home/ubuntu/workspace/noise-checker/docs/02-database-design.md#L132), [02-database-design.md:L378](file:///home/ubuntu/workspace/noise-checker/docs/02-database-design.md#L378)
*   **문제점:** `term_evidence` 테이블의 `excerpt` 필드는 "저작권 고려, 짧게" 저장하도록 권고하고 있으나, 수집기(collector)가 자동으로 이를 수집할 때 텍스트 길이 제한에 대한 물리적 제약(CONSTRAINT 또는 길이 검증)이 스키마 수준에서 정의되어 있지 않아 뉴스 본문의 대량 복제본이 데이터베이스에 오적합 저장될 저작권 리스크가 상존합니다.
*   **개선 제안:** `excerpt` 필드에 VARCHAR(500) 등으로 데이터베이스 수준의 최대 길이 제약을 걸거나, 수집기 API 클라이언트에서 특정 글자 수(예: 300자) 이상은 자동으로 잘라내고 원문 URL 및 메타데이터만 활용하도록 코드 레벨에서 엄격히 제한해야 합니다.
