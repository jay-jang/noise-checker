# 상호 리뷰 판정 원문 — Antigravity의 평가 (리뷰 A·B 판정)

# noise-checker 아키텍처 상호 리뷰(Cross-Review) 보고서 — Antigravity

본 보고서는 noise-checker 프로젝트(한국어 혐오 용어/표식 검출 자문 API)에 대해 작성된 **리뷰 A (Claude의 독립 리뷰)**와 **리뷰 B (Codex의 독립 리뷰)**의 Critical/Major 발견 사항에 대해 본인(리뷰 C 작성자, Antigravity)의 관점에서 교차 평가한 결과입니다.

---

## 1. 리뷰 A (Claude) 발견 사항 평가

### A-C1. 핵심 가치제안(유래/origin_story 제공)과 핵심 라이선스 제약(나무위키 NC + 위키 SA)이 정면 충돌 — 산출물의 ShareAlike 오염이 사업모델을 잠식
* **판정**: **동의 (Agree)** / **합의 (Consensus)** (리뷰 B-C4 및 본인 리뷰 C-Major 5와 정합)
* **근거**: [02-database-design.md](file:///home/ubuntu/workspace/noise-checker/docs/02-database-design.md#L308-L320) §3.10에 따르면 라이선스 소스가 1건이라도 포함되면 릴리스 아티팩트의 라이선스가 `CC BY-SA 4.0`으로 전파되지만, 이로 인해 API 응답을 받는 B2B 고객사에게 저작권 의무(SA)가 전이되는지에 대한 구체적인 비즈니스·법적 리스크 분석과 우회 설계가 결여되어 있습니다.

### A-C2. "사전 매칭 → 문맥 분류" 캐스케이드의 근본 한계: 최다 사고 유형(도그휘슬/회색지대)은 정의상 사전 매칭으로 안 잡힌다 — 솔루션 접근과 사고 분포의 미스매치
* **판정**: **동의 (Agree)**
* **근거**: [01-research-report.md](file:///home/ubuntu/workspace/noise-checker/docs/01-research-report.md#L163) §6에서 남성혐오 도그휘슬이 실사고 최다 유형이며 높은 부인가능성을 지닌다고 분석했음에도, [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L43-L45) §2의 파이프라인은 사전 매칭(단계 1)을 1차 진입점으로 삼고 있어 사전에 없는 최신 변형 도그휘슬을 놓칠 구조적 한계가 큽니다.

### A-C3. M1 시드 300+ 검수가 임계경로인데, 검수자(도메인 전문가)의 신뢰성·일관성·심리적 부담에 대한 계획이 전무 — 1인 운영 가정이 비현실적
* **판정**: **동의 (Agree)** / **합의 (Consensus)** (리뷰 B-C2 및 본인 리뷰 C-Major 6과 정합)
* **근거**: [05-implementation-plan.md](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L37-L40) M1 및 [04-update-pipeline.md](file:///home/ubuntu/workspace/noise-checker/docs/04-update-pipeline.md#L88) §4에서 1인 운영 시 세션 분리만을 명시하고 있으나, 혐오 표현에 대한 지속 노출로 인한 검수자 정신건강 대책(블러 처리 등) 및 검수자 편향을 방지하기 위한 정량 지표(IAA 등) 계획이 부재합니다.

### A-M1. 위험도 공식 `f(severity, match_confidence, context_score, category, composite_score)`이 정의되지 않은 채 5개 마일스톤이 의존
* **판정**: **동의 (Agree)**
* **근거**: [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L65-L70) §2 단계 4 및 [05-implementation-plan.md](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L12) M2 출시 기준이 미정의된 위험도 산정 함수 `f()`에 의존하고 있어, 실제 차단(block) 등급 부여 및 골든셋 테스트 통과 여부를 판단할 구체적인 정책과 가중치가 미비합니다.

### A-M2. KcELECTRA 기반(BERT 계열) 모델 의존 — 학습 데이터 라이선스 전이 리스크가 "주의"로만 처리됨
* **판정**: **동의 (Agree)** / **합의 (Consensus)** (리뷰 B-M10 및 본인 리뷰 C-Major 3과 정합)
* **근거**: [01-research-report.md](file:///home/ubuntu/workspace/noise-checker/docs/01-research-report.md#L117) §3에서 딥러닝 모델 가중치로의 CC BY-SA 라이선스 전이 우려를 자각하고 있음에도, 이를 상업 API인 [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L136)에서 여전히 기본 스택으로 설정하고 있어 법적 분쟁의 불확실성을 안고 있습니다.

### A-M3. p95 150ms 목표에 ML/LLM 폴백·이미지·콜드스타트가 숨어 있고, 동기 경로에 외부 LLM API(Claude) 호출이 들어옴
* **판정**: **동의 (Agree)**
* **근거**: [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L60) §2 단계 3에 따라 동기 응답 경로 상에 외부 API(Claude) 호출이 포함되어 있어, 대기 시간의 가변성과 네트워크 지연으로 인해 [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L158) §7에 정의된 동기식 p95 500ms 지연 목표를 안정적으로 충족하기 어렵습니다.

### A-M4. 이미지 손모양 감지의 오탐 처리는 명문화됐으나, "집게손가락 자동검출 자체가 사회적 논란을 재생산"하는 메타 리스크 미평가
* **판정**: **동의 (Agree)**
* **근거**: [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L153) §6에서 집게손가락을 `warn`으로 격리하고 반론을 병기하도록 설계하였으나, 자동화 검출 도구의 존재가 B2B 고객사의 부당한 인사 조치(해고, 징계)를 가속화하는 윤리적·평판 리스크 및 사용 제한 가이드라인 강제 방안이 누락되어 있습니다.

### A-M5. composite_rule의 co_occurrence/proximity가 검사 엔진 성능·복잡도에 미치는 영향 미분석
* **판정**: **동의 (Agree)**
* **근거**: [02-database-design.md](file:///home/ubuntu/workspace/noise-checker/docs/02-database-design.md#L263-L282) §3.8에 추가된 복잡한 근접도(proximity) 및 동시출현 규칙이 다수 매칭 후보들과 결합할 때 엔진의 평가 연산 복잡도(O(N²))가 증가하여 지연 시간 목표에 미칠 성능적 영향이 검증되지 않았습니다.

### A-M6. 다중 레플리카 환경에서 사전 버전 불일치 — "향후 과제"로 미뤘으나 베타(M6)에 이미 문제
* **판정**: **동의 (Agree)**
* **근거**: [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L159) §7에서는 다중 레플리카 일괄 전환을 향후 과제로 미루었지만, [05-implementation-plan.md](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L83)에 명시된 M6 베타 VM 2대 기반 멀티 인스턴스 서빙 구조상 인스턴스 간 일시적인 사전 버전 불일치 현상이 당장 발생하게 됩니다.

### A-M7. KcELECTRA(KcELECTRA-base-v2022)는 2022 시점 모델 — 2024~26 신조어 토크나이저 커버리지 한계
* **판정**: **동의 (Agree)**
* **근거**: [01-research-report.md](file:///home/ubuntu/workspace/noise-checker/docs/01-research-report.md#L117) §3의 `KcELECTRA-base-v2022` 기반 subword 토크나이저는 [01-research-report.md](file:///home/ubuntu/workspace/noise-checker/docs/01-research-report.md#L161) §6에 언급된 2024~2026년 실사고 신조어를 처리할 때 형태가 깨진 형태로 분절(Segmentation)하여 문맥 분류 성능 저하를 야기합니다.

### A-M8. KOLD를 평가/참조용으로 쓴다고 했으나 라이선스 "명시 없음"인데 must_catch 채점 기준 후보로 등장 — 격리 일관성 허점
* **판정**: **동의 (Agree)**
* **근거**: [04-update-pipeline.md](file:///home/ubuntu/workspace/noise-checker/docs/04-update-pipeline.md#L126) §7에서 KOLD를 라이선스 불명으로 취급하여 릴리스 빌드에서 배제한다고 설정해두고도, [06-test-plan.md](file:///home/ubuntu/workspace/noise-checker/docs/06-test-plan.md#L48) §2.3의 벤치마크 평가 자산으로 사용하도록 설계하여 불명 라이선스 자원의 내부 격리 정책에 위배됩니다.

### A-M9. 정규화 §4.5 "반복 문자 압축 안 함"과 변형 회피의 충돌 — "ㅋㅋㅋ운지" vs "운우운지" 류 누락 경로
* **판정**: **동의 (Agree)**
* **근거**: [02-database-design.md](file:///home/ubuntu/workspace/noise-checker/docs/02-database-design.md#L341) §4.5에 명시된 규칙으로 인해, 자모나 한글 음절을 불규칙적으로 삽입/반복(예: "운우지")하는 회피 공격에 대처하기 위해 비정상적으로 많은 변형(`term_variant`)을 데이터베이스에 등재해야 하는 비효율이 존재합니다.

---

## 2. 리뷰 B (Codex) 발견 사항 평가

### B-C1. 핵심 제품 리스크가 “혐오 검출”보다 “논란 가능성 판정”에 가까운데, 판정 체계가 법적·제품적으로 충분히 재정의되지 않았습니다.
* **판정**: **동의 (Agree)**
* **근거**: [01-research-report.md](file:///home/ubuntu/workspace/noise-checker/docs/01-research-report.md#L143) §5에서 법적 리스크를 줄이기 위해 단순한 자문 형식의 응답을 규정했으나, [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L102-L122) §4의 API 예시에서는 `overall_risk: "block"` 및 "제거하거나 교체"하도록 하는 단정적 권고 방식을 반환하고 있어 모순됩니다.

### B-C2. M1의 “핵심 용어 300+개” 목표는 아직도 데이터 현실성과 검수 병목을 과소평가합니다.
* **판정**: **동의 (Agree)** / **합의 (Consensus)** (리뷰 A-C3 및 본인 리뷰 C-Major 6과 정합)
* **근거**: [05-implementation-plan.md](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L11) M1에서 요구하는 3~4주 일정 내 300개 용어 active 승인은 [04-update-pipeline.md](file:///home/ubuntu/workspace/noise-checker/docs/04-update-pipeline.md#L84-L89) §4의 엄격한 체크리스트와 2인 세션 검수 프로세스를 고려할 때 인력 리소스 측면에서 일정이 지나치게 낙관적으로 산정되어 병목을 야기합니다.

### B-C3. 이미지 방향성이 제품 핵심 사고 유형과 맞지만, 기술적 성공 기준이 지나치게 낙관적입니다.
* **판정**: **동의 (Agree)** / **합의 (Consensus)** (본인 리뷰 C-Major 8과 정합)
* **근거**: [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L79) §3의 랜드마크 기반 분류 모델은 가려짐이나 일러스트 등 텍스처 변이가 극심한 실무 마케팅 이미지 환경에서 랜드마크 붕괴로 오탐(FP)을 극대화할 위험이 크며, [05-implementation-plan.md](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L14) M4의 재현율 0.9 달성 기준은 극도로 낙관적입니다.

### B-C4. 라이선스 전략은 방어적으로 보이지만, CC BY-SA 기반 상업 API의 산출물/DB 파생물 문제를 충분히 좁히지 않았습니다.
* **판정**: **동의 (Agree)** / **합의 (Consensus)** (리뷰 A-C1 및 본인 리뷰 C-Major 5와 정합)
* **근거**: [02-database-design.md](file:///home/ubuntu/workspace/noise-checker/docs/02-database-design.md#L316) §3.10의 `effective_license` 정보만으로는 CC BY-SA 라이선스 요약 문장이 API 응답을 통해 B2B 고객사의 시스템에 직접 전파될 때 생기는 법적 책임의 한계를 명확히 통제하거나 보장할 수 없습니다.

### B-M1. “사전 기반 매칭 → 문맥 분류 → 이미지” 순서는 대체로 타당하지만, 문맥 분류가 너무 늦습니다.
* **판정**: **동의 (Agree)** / **합의 (Consensus)** (본인 리뷰 C-Minor 9와 정합)
* **근거**: [05-implementation-plan.md](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L12) M2 텍스트 MVP 릴리스 기준에서 문맥 분류기가 배제되어 있어, ambiguous 항목의 동음이의어(예: "운지"버섯)가 필터링 없이 그대로 매칭 경고로 발생하게 되므로 조기 파일럿 테스트를 진행하기에 사용성이 심각하게 저하됩니다.

### B-M2. 한국어 NLP 리스크가 형태소 분석 수준으로 축소되어 있습니다.
* **판정**: **동의 (Agree)**
* **근거**: [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L41) §2 단계 0에서 Kiwi 형태소 분석기와 조사 결합 여부 판단에 의존하고 있어, 형태소 분절 경계만으로 포착하기 어려운 조롱성 인용이나 비표준 어미("-노"의 부자연스러운 종결 등)의 문체적 도그휘슬을 정밀 탐지하는 데 한계가 있습니다.

### B-M3. 변형 회피 대응은 공격자 모델이 불명확합니다.
* **판정**: **동의 (Agree)**
* **근거**: [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L50-L55) §2 단계 2의 퍼지 및 skip-char 탐지는 구현 수준의 규칙만 나열할 뿐, 변형 탐지 시 발생하는 오탐(FP)과 미탐(FN)의 허용치 제어 기준이나 우회 패턴 유형에 따른 대응 전략이 정립되어 있지 않습니다.

### B-M4. 데이터 전략이 “출처 있는 용어”와 “검출해야 할 용어”의 간극을 과소평가합니다.
* **판정**: **동의 (Agree)**
* **근거**: [02-database-design.md](file:///home/ubuntu/workspace/noise-checker/docs/02-database-design.md#L98) §3.2의 데이터 스키마는 명확한 `evidence`가 있어야만 `active` 상태로 전환될 수 있게 제한하므로, 공식 보도나 위키에 오르기 전 극초기 유포 밈(도그휘슬)을 추적하기 위해 임시로 탐지하는 `watchlist` 같은 과도기적 단계를 지원할 수 없습니다.

### B-M5. 뉴스 기반 신규 포착은 편향된 신호원입니다.
* **판정**: **반박 (Reject)**
* **근거**: [04-update-pipeline.md](file:///home/ubuntu/workspace/noise-checker/docs/04-update-pipeline.md#L10-L15) §1 및 §2에 따르면, 뉴스 모니터링 외에도 위키 변경(wiki-watcher), 오픈소스 및 데이터셋 모니터링(repo-watcher), 트렌드(trends-checker), 고객 피드백(feedback-intake), 그리고 비사전 고위험 문장 마이닝(ool-warning-miner) 채널이 모두 독립적으로 동작하며 `candidate_queue`의 `signal_score`로 다각적으로 통합 점수화되도록 설계되어 있습니다.

### B-M6. 운영 로그/프라이버시 정책이 제품 학습 전략과 충돌합니다.
* **판정**: **부분동의 (Partial)**
* **근거**: [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L161) §7에 명시된 24시간 내 데이터 파기 및 원문 미기록 정책은 B2B 개인정보보호 측면에서 타당하지만, 수집계의 오탐 분석용 문장 클러스터링([04-update-pipeline.md](file:///home/ubuntu/workspace/noise-checker/docs/04-update-pipeline.md#L55) §2.⑥)을 보완하기 위해 개인정보를 마스킹하여 보존하는 식별 정보 필터링과 상세 아키텍처는 추가 정의가 필요합니다.

### B-M7. API 응답 예시가 법적 포지셔닝과 아직 불일치합니다.
* **판정**: **동의 (Agree)** (B-C1과 중복)
* **근거**: [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L102-L122) §4의 API 예시는 `overall_risk: "block"` 및 강제적인 대체 권고를 제시하여, [01-research-report.md](file:///home/ubuntu/workspace/noise-checker/docs/01-research-report.md#L143) §5에서 요구된 "리스크 확률 및 자문 의견 전달"이라는 법적 방어 목적의 제품적 한계와 모순을 빚습니다.

### B-M8. DB 스키마가 검수 상태와 릴리스 상태를 충분히 분리하지 않습니다.
* **판정**: **동의 (Agree)**
* **근거**: [02-database-design.md](file:///home/ubuntu/workspace/noise-checker/docs/02-database-design.md#L98) §3.2 및 §3.10의 빌드 아티팩트 생성 로직은 단순히 `status='active'`인 전원을 일괄 추출하므로, 고객군별 민감도나 릴리스 채널(텍스트/이미지 전용 구분 등)에 따라 빌드를 조건부 배포할 수 있는 릴리스 정책 메타데이터 속성이 존재하지 않습니다.

### B-M9. 실사고 incident를 회귀 테스트로 쓰는 전략은 좋지만, 저작권·명예훼손 리스크가 테스트 저장소에서도 남습니다.
* **판정**: **동의 (Agree)**
* **근거**: [02-database-design.md](file:///home/ubuntu/workspace/noise-checker/docs/02-database-design.md#L245) §3.7에서 텍스트 회귀 테스트 목적으로 `sample_text`에 기업 실명 및 혐오 발언 사례를 보존하도록 유도하지만, [06-test-plan.md](file:///home/ubuntu/workspace/noise-checker/docs/06-test-plan.md#L10) §1의 평문 `must_catch.jsonl`이 저장소에 평문 커밋되거나 CI 파이프라인에 노출되면 외부 전파(공연성)에 따른 법적 리스크가 발생합니다.

### B-M10. KcELECTRA 파인튜닝 계획은 라이선스·편향·라벨 불일치 리스크를 과소평가합니다.
* **판정**: **동의 (Agree)** / **합의 (Consensus)** (리뷰 A-M2 및 본인 리뷰 C-Major 3과 정합)
* **근거**: [01-research-report.md](file:///home/ubuntu/workspace/noise-checker/docs/01-research-report.md#L92) §2에서 융합 매핑 표를 두고 있으나, 수집 및 어노테이션 가이드라인이 상이한 다수의 이종 데이터셋(SelectStar, UnSmile 등)을 단순 병합하여 문맥 분류기([03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L58-L61) §2 단계 3)를 파인튜닝할 경우 분류 가중치가 극도로 왜곡되거나 데이터 전파 리스크가 발생할 여지가 큽니다.

### B-M11. 성능 목표가 입력 조건을 붙였지만, 실제 고객 워크플로우와 분리되어 있습니다.
* **판정**: **동의 (Agree)**
* **근거**: [03-architecture.md](file:///home/ubuntu/workspace/noise-checker/docs/03-architecture.md#L158) §7에서는 500자 이하 단문 성능 수치(p95 150ms)만을 지연 목표로 명시하고 있으나, B2B 고객의 실무 워크플로우인 상세페이지 통째 검수나 일괄 캠페인 카피 배치 검수(`/v1/check/batch`)를 지원하기 위한 처리량(Throughput) 기반 성능 목표(SLO) 및 부하 감당 방안이 결여되어 있습니다.

### B-M12. 검수 콘솔이 핵심 제품인데 MVP로 과소취급됩니다.
* **판정**: **동의 (Agree)** / **합의 (Consensus)** (본인 리뷰 C-Major 6과 정합)
* **근거**: [05-implementation-plan.md](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L60) M5 단계에 검수 콘솔 MVP를 단순하게 구현하려는 계획은, 수작업 공수가 극대화되는 [05-implementation-plan.md](file:///home/ubuntu/workspace/noise-checker/docs/05-implementation-plan.md#L28) M1 단계(300+개 용어 구축) 수집 및 정밀 라이선스/법무 체크리스트 검증의 생산성 저하를 과소평가했습니다.

### B-M13. 이전 리뷰 #12 반영이 문서 간 불완전합니다.
* **판정**: **동의 (Agree)**
* **근거**: 이전 적대적 리뷰 결과 보고서인 [review-2026-06-04.md](file:///home/ubuntu/workspace/noise-checker/reports/review-2026-06-04.md#L19) 이슈 12에서는 수집/후보 큐의 스키마 반영이 완료되었다고 기록했으나, 실제 [04-update-pipeline.md](file:///home/ubuntu/workspace/noise-checker/docs/04-update-pipeline.md#L65) §3의 `candidate_queue` 스키마에는 단지 `payload JSONB`로만 기술되어 있어 조합 규칙(combination_rules)의 데이터 적재 형태나 정합성 제약이 누락되어 있습니다.

### B-M14. 이전 리뷰 #17 반영이 제공 문서에서는 확인되지 않습니다.
* **판정**: **동의 (Agree)**
* **근거**: [review-2026-06-04.md](file:///home/ubuntu/workspace/noise-checker/reports/review-2026-06-04.md#L24) 이슈 17에 의거하여 회피(evasion) 케이스의 릴리스 게이트 반영 및 정본 머지 소유권이 서술되었다고 보고되었으나, 실제 제공된 [06-test-plan.md](file:///home/ubuntu/workspace/noise-checker/docs/06-test-plan.md#L12) §1에는 두 에이전트 소유권 승인 절차나 규칙이 명시적으로 포함되어 있지 않습니다.

---

## 3. 종합 평가 결과

### 3.1. 합의 Top 5 (최우선 보완 항목)

1. **CC BY-SA 라이선스 전파 오염 및 B2B API 고객 전사 의무 전이 리스크** (A-C1, B-C4 합의)
   * *이유*: `origin_story` 요약 등 CC BY-SA 소스로부터 요약 가공된 데이터가 B2B API 응답 페이로드를 타고 고객사 시스템에 전달될 때, 고객사의 최종 산출물에도 ShareAlike 의무가 도미노 전파될 수 있는 치명적 법적/비즈니스적 리스크가 존재하며 이에 대한 우회 방안이 없습니다.
2. **M1 단계 300+개 사전 구축 병목 및 검수 콘솔 배치 선후관계 모순** (A-C3, B-C2, C-Major 6 합의)
   * *이유*: 300개 이상의 초기 시드 사전을 풍부한 출처 및 유래와 함께 승인하는 M1은 전체 마일스톤 중 가장 큰 병목 구간입니다. 그러나 효율적인 검수 도구인 검수 콘솔(Streamlit)의 일정이 M5에 가 있어 M1에서는 로우 쿼리 등 비효율적인 수동 검수를 강제하게 만듭니다. 또한 1인 운영 시 검수 편향 방지(IAA 등) 계획도 미비합니다.
3. **이미지 표식 검출의 극심한 오탐 및 사회적 갈등 재생산 메타 리스크** (B-C3, C-Major 8, A-M4 합의)
   * *이유*: 마케팅 일러스트나 저해상도 이미지 특성상 기하학적 손동작 랜드마크 분석은 무수한 오탐(FP)을 낳습니다. 더욱이, 이러한 자동 검출기의 존재가 B2B 고객사의 부당 해고나 디자이너 징계 등 2차 평판 리스크를 가속할 우려가 있음에도 API 페이로드에 주의/인사조치 활용 금지 고지를 강제하는 등의 가이드라인 설계가 빠져 있습니다.
4. **문맥 분류기(KcELECTRA) 학습/적재 한계 및 라이선스·라벨 모호성** (A-M2, A-M7, B-M10, C-Major 3 합의)
   * *이유*: 2022년 시점 모델에 의한 신조어 토크나이저의 비정상적 분절, 서로 규격이 다른 외부 코퍼스의 이종 결합 파인튜닝 시 의미 중첩 문제, 그리고 CC BY-SA 학습 셋 전이에 대한 법적 우려가 종합적으로 지적되었습니다.
5. **사전 매칭 중심의 탐지 파이프라인과 신규 도그휘슬 탐지 간의 미스매치** (A-C2, B-M4 합의)
   * *이유*: 마케팅 사고의 최빈값인 도그휘슬은 고정 사전에 들어있지 않거나 끊임없이 표면형을 바꾸기 때문에, AC 스캔(단계 1) 중심의 그물망으로는 방어율이 급격히 떨어집니다. 보도 이전의 밈들을 포착해 내부 관리하기 위한 `watchlist` 등의 중간 완충 상태 설계도 필요합니다.

### 3.2. 기각 권고 (오독 및 과장으로 기각할 항목)

* **B-M5. 뉴스 기반 신규 포착은 편향된 신호원입니다 (기각)**
  * *이유*: [04-update-pipeline.md](file:///home/ubuntu/workspace/noise-checker/docs/04-update-pipeline.md#L10-L15) §1 및 §2에서 뉴스(news-monitor) 외에도 위키 감시(wiki-watcher), 저장소 감시(repo-watcher), 구글 트렌드(trends-checker), 고객 피드백(feedback-intake), 그리고 비사전 고위험 문장 클러스터링(ool-warning-miner) 등의 다각적인 채널을 설정하였으며, 이를 `signal_score`로 병합하여 점수화하도록 이미 설계해 두었으므로 특정 채널에 과도하게 의존한다는 지적은 프로젝트 문서의 실제 설계를 오독한 과장입니다.

### 3.3. 심각도 재조정 권고

1. **B-M12 (검수 콘솔 MVP로 과소취급) 및 C-Major 6 (검수 콘솔 후순위 배치)**: `Major` → `Critical` 상향
   * *이유*: 사전의 유래 설명(origin_story)과 객관적 근거주의가 서비스의 핵심 자산이며, M1(3~4주)은 300+개 항목에 대해 개별 출처, 라이선스, 카테고리, severity 등을 수동 검수해야 하는 전체 일정의 임계경로(Critical Path)입니다. 검수 콘솔의 지원 없이 이 단계를 수행하는 것은 마일스톤 전체를 연쇄 지연시키는 요인이 확실하므로 이 일정을 최우선으로 앞당기는 것은 `Critical` 수준의 아키텍처적 조치입니다.
2. **B-M6 (운영 로그/프라이버시 정책과 제품 학습 전략 충돌)**: `Major` → `Minor` 하향
   * *이유*: B2B API의 법적 가드레일 확립을 위해 24시간 내 원문 파기를 선언한 기본 방침은 비즈니스 안정성 측면에서 반드시 수호해야 할 가치입니다. 이를 과도하게 완화하는 것보다, 비식별화 패킷(PII 마스킹 필터 등)의 추가 설계 보강 수준으로 처리하는 것이 타당하므로 `Minor` 이슈로 하향 조정할 것을 권고합니다.
