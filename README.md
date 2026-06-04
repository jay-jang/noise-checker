# Noise Checker — 악성 커뮤니티 용어/표식 검사 서비스

악성 커뮤니티(일베, 극단적 여혐/남혐 사이트 등)에서 통용되는 **용어·문구·이미지 표식**이
일반 문장이나 마케팅 자료에 실수로 쓰이는 것을 사전에 검출하는 브랜드 세이프티 서비스.

> 핵심 차별점: 단순 "위험 단어 목록"이 아니라, 모든 항목에 **출처(source)와 유래(origin)**를
> 검증 가능한 형태로 붙여서 "왜 위험한지"를 근거와 함께 답한다.

## 무엇을 검사하나

| 입력 | 검사 방식 | 예 |
|---|---|---|
| 단어/문장 | 정규화 → 다중 패턴 매칭 → 변형/퍼지 → 문맥 분류(ML/LLM) | 광고 카피, 상품명, SNS 게시문 |
| 이미지 | OCR→텍스트 검사, 표식 매칭(pHash/CLIP), 손모양 감지 | 포스터, 일러스트, 짤방 |

## 문서 구성

| 문서 | 내용 |
|---|---|
| [01-research-report.md](docs/01-research-report.md) | 데이터 소스 조사 결과 — 공개 데이터셋, 커뮤니티 용어 출처, 이미지 표식, 라이선스 |
| [02-database-design.md](docs/02-database-design.md) | Lexicon DB 스키마 — 출처/유래 추적, 변형, 상태기계, 릴리스 버저닝 |
| [03-architecture.md](docs/03-architecture.md) | 서비스 아키텍처 — 검사 파이프라인, API 설계, 기술 스택 |
| [04-update-pipeline.md](docs/04-update-pipeline.md) | 주기적 업데이트 시스템 — 수집기, 검수 흐름, 릴리스 자동화 |
| [05-implementation-plan.md](docs/05-implementation-plan.md) | 단계별 구현 계획 (마일스톤, 담당 에이전트) |
| [06-test-plan.md](docs/06-test-plan.md) | 테스트 전략 — 골든셋, 오탐/미탐 평가, 레드팀 |
| [07-agents-and-skills.md](docs/07-agents-and-skills.md) | 서브 에이전트 구성 — 역할/스킬/기술 스택 |

## 서브 에이전트

`.claude/agents/`에 8개 에이전트가 정의되어 있다 (`@lexicon-researcher`, `@data-curator`,
`@variant-engineer`, `@detection-engineer`, `@ml-engineer`, `@image-engineer`,
`@pipeline-engineer`, `@qa-redteam`). 상세는 [07 문서](docs/07-agents-and-skills.md).

## 윤리·법적 원칙

- **방어적 목적 한정**: 혐오표현 생산/유포가 아닌 검출·예방용.
- **근거주의**: 근거 없는 항목은 검사에 사용하지 않는다 (`draft` 상태 격리).
- **사람 검수**: 자동 수집은 후보까지만, 사전 등재는 사람이 승인.
- **저작권/라이선스 준수**: 데이터셋 라이선스 분류, 최소 인용, 나무위키 CC BY-NC-SA 표기.
- **역이용 방지**: 변형 생성 규칙·임계값 비공개, API 키 발급제.
