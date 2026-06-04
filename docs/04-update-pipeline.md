# 04. 주기적 업데이트 시스템 — 수집 → 검수 → 빌드 → 릴리스

> 원칙 1: **자동화는 후보 생성까지, 등재는 사람이.** (법적 방어선이자 품질 방어선)
> 원칙 2: **합법 소스만.** 커뮤니티 직접 크롤링 금지(잡코리아-사람인 판결, 대법원 2021도1533), 나무위키 크롤링 금지(403+NC+약관).
> 원칙 3: 모든 수집물은 **수집 시점 스냅샷 + 출처 메타데이터**와 함께 저장.

## 1. 전체 흐름

```
        ┌──────────── 수집기 (Collectors) ────────────┐
        │ ① news-monitor      (일간, 네이버 뉴스 API)   │
        │ ② wiki-watcher      (주간, 위키백과/페미위키)  │
        │ ③ repo-watcher      (주간, GitHub/HF)        │
        │ ④ trends-checker    (주간, Google Trends)    │
        │ ⑤ feedback-intake   (상시, /v1/feedback)     │
        │ ⑥ ool-warning-miner (상시, 사전外 고위험 문장) │
        └──────────────────┬──────────────────────────┘
                           ▼
                  [후보 큐 candidate_queue]
                  (자동 점수화: 신호 강도/중복/긴급도)
                           ▼
                  [검수 콘솔] ── 사람 승인/반려 ──→ Lexicon DB (status 전이)
                           ▼
                  [사전 빌드] 골든셋 회귀 게이트 → diff 리포트 → 승인
                           ▼
                  [릴리스 배포] 검사 API 핫리로드 (CalVer)
```

## 2. 수집기 상세

### ① news-monitor (일간 — 가장 중요한 신규 신호원)
- **근거**: 신규 도그휘슬은 거의 항상 언론 보도로 먼저 표면화됨 (노무한 박수, 들켰노, 탱크데이 모두 보도가 1차 신호).
- 네이버 뉴스 검색 API + **BigKinds 뉴스빅데이터 API**(한국언론진흥재단, 8천만 건 — 과거 사례 발굴 겸용)로 키워드 셋 질의: `일베 용어 논란`, `혐오 표현 광고`, `남혐 논란`, `여혐 마케팅`, `집게손가락 논란`, `(주요 브랜드명) + 사과 + 논란` 등. 키워드 셋 자체도 DB 관리.
- 처리: 제목/링크/날짜만 저장(본문 전체 저장 금지 — 저작권) → LLM이 기사에서 **문제가 된 표현·표식 추출** → 후보 엔트리 초안 생성(incident + term 후보 + **표식 논란이면 `new_marker` 후보**를 candidate_queue로 동시 라우팅) → 검수 큐. incident는 기본 `legal_reviewed=false, disclosable=false`로 적재 (자동 노출 불가 — 02 §3.7).
- 기존 사전과 매칭되면 해당 incident만 추가(용어 활동성 갱신).

### ② wiki-watcher (주간)
- 위키백과(CC BY-SA): '집게손가락 음모론', '일베저장소의 사건 및 사고', '대한민국의 인터넷 신조어 목록' 등 감시 문서 목록의 개정 이력을 MediaWiki API로 폴링 → diff에서 신규 사례/용어 추출. 월간 전체 덤프(dumps.wikimedia.org) 동기화 병행.
- 페미위키(CC BY-SA): 남혐 용어 문서 갱신 감시.
- 리브레위키(CC BY-SA): 일베 사건사고 문서 등 — 나무위키의 청정 대안 소스.
- 수집물은 ShareAlike 전파 의무 추적을 위해 `source.license` 명기. 인용 시 archive.org 등록.

### ③ repo-watcher (주간)
- GitHub: korcen(룰셋 커밋 diff — 신규 패턴), korean-profanity-resources / AwesomeKorean_Data (신규 데이터셋 등재).
- HuggingFace hub API: 한국어 혐오표현 신규 데이터셋/모델 검색.
- 출력: 신규 자원 발견 알림 + 라이선스 1차 자동 판독 → data-curator 검토 큐.

### ④ trends-checker (주간, 보조 신호)
- 의심 용어 목록(draft 포함)의 검색량 추이 → 급상승 시 검수 우선순위 상향. 단독으로 후보 생성하지 않음.

### ⑤ feedback-intake (상시)
- `/v1/feedback`의 미탐 신고 = 신규 용어 1차 발굴원 (업계 '화이트 일베' 수동 모니터링을 흡수하는 채널).
- 오탐 신고 = safe_contexts/화이트리스트 보강 + must_pass 골든셋 후보.

### ⑥ ool-warning-miner (상시)
- 검사 API에서 사전 매칭 0건인데 문장 분류기가 고위험 판정한 입력(고객 옵트인 데이터 한정) → 신조어 후보 클러스터링 → 주간 요약을 검수 큐로.

### 이미지 표식 수집의 단계 구분
- **M4 이전**: `image_marker`/`marker_reference_image`는 image-engineer·lexicon-researcher가 01 §1.E 전략(위키미디어 라이선스 명시본 + 뉴스 보도 기반 자체 재현 제작)으로 **수동 큐레이션**. ①의 `new_marker` 후보는 표식의 존재·출처 기록까지만.
- **M4+**: wiki-watcher가 감시 문서에 임베드된 위키미디어 커먼즈 라이선스 명시 이미지를 `license_ok` 후보로 자동 추출하는 경로 추가 (후속 고도화).

## 3. 후보 큐와 자동 점수화

```sql
CREATE TABLE candidate_queue (
    id           BIGSERIAL PRIMARY KEY,
    payload      JSONB NOT NULL,          -- term/marker/incident 후보 초안
    kind         TEXT NOT NULL,           -- 'new_term','new_variant','new_marker','incident','deprecation'
    collector    TEXT NOT NULL,           -- 수집기 ID
    signal_score REAL NOT NULL,           -- 신호 강도 (보도 건수, 신고 수, 트렌드 기울기)
    urgency      TEXT NOT NULL DEFAULT 'normal',  -- 'urgent'(보도 진행 중 사고) / 'normal' / 'low'
    dedup_key    TEXT NOT NULL,           -- normalized_key 기반 중복 방지
    status       TEXT NOT NULL DEFAULT 'pending', -- pending/approved/rejected/merged
    created_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE (dedup_key, kind)
);
```

- `urgent` 항목(현재 보도 중인 신규 사고)은 즉시 알림 → 24h 내 검수 목표 → 필요 시 핫픽스 릴리스.
- LLM 사전 분석을 후보에 첨부: 추정 유래, 추정 카테고리, 동음이의어 위험, 권장 severity — **검수자 보조 자료일 뿐 자동 승인 금지.**

## 4. 검수 워크플로우 (human-in-the-loop)

1. 검수자는 후보의 근거(출처 링크, 발췌)를 확인하고 부족하면 lexicon-researcher 에이전트로 추가 조사 지시.
2. 체크리스트: ① origin 출처 ≥ 1 (청정 라이선스) ② 동음이의어 검토 + safe_contexts ③ severity 산정 근거 ④ 카테고리 ⑤ 법무 플래그 — term의 특정인 실명 여부 **+ incident의 기업·개인 실명/sample_text 노출 여부**(`disclosable=true` 전환은 법무 검토 필수).
   **검수 강도 차등**: severity 5 또는 법무 플래그 항목만 풀 체크리스트 + 2차 검토. 실사고 역추출(evidence 자동 확보) 및 저위험 항목은 경량 체크리스트로 단위 공수 절감.
3. 승인 → `term.status = active`, `review_log` 기록. 반려 → 사유와 함께 rejected.
4. **검수 권한 분리**: 후보 생성자(파이프라인/에이전트)는 승인 불가. 1인 운영 시에도 생성 세션과 승인 세션 분리.

## 5. 사전 빌드 & 릴리스 게이트

```
trigger (주간 정기 / urgent 핫픽스)
  → active 항목 추출 → 정규화 키 재계산 → 변형 자동 생성(verified만 포함 옵션)
  → 오토마톤/패턴/이미지 인덱스 컴파일 → manifest(체크섬, normalizer_code_version)
  → [게이트 0] 라이선스 화이트리스트: 릴리스 아티팩트에 컴파일되는 모든 active 항목의
      연결 evidence source 전부가 license_class ∈ {permissive, share_alike}여야 통과.
      noncommercial/no_derivatives/restricted/unknown이 하나라도 있으면 해당 항목 제외 + 검수 큐 반려.
      share_alike 포함 시 effective_license 갱신 + attribution.json 자동 생성, 누락 시 차단.
      (KOLD·AI Hub 등 문장 코퍼스는 data/corpus/ 격리 ML 학습 전용 — 이 게이트의 대상 아님)
  → [게이트 1] 데이터 무결성: evidence ≥ 1, URL 생존(또는 archive), 필수 필드
  → [게이트 2] 골든셋 회귀: must_catch/must_pass/evasion — 직전 릴리스 대비 신규 실패 0건
      (must_pass 채점은 06 §1의 등급별 규칙 적용: ambiguous 항목은 M3 전까지 block만 실패로 카운트)
  → [게이트 3] diff 리포트 생성 → 사람 승인
  → 릴리스 (CalVer: v2026.06.04-1) → 검사 API 핫리로드 → 평가 리포트 보존
```

## 6. 운영 주기 요약

| 작업 | 주기 | 자동화 수준 |
|---|---|---|
| 뉴스 모니터링 | 일간 | 자동 수집 + 사람 검수 |
| 위키/저장소 감시 | 주간 | 자동 diff + 사람 검수 |
| 정기 릴리스 | 주간 | 게이트 자동, 승인 수동 |
| 긴급 핫픽스 | 사고 발생 시 24h 내 | 알림 자동, 등재 수동 |
| 모델 재학습 (신조어 반영) | 분기 | ml-engineer 주관 |
| 사어화(deprecation) 검토 | 분기 | 후보 자동 제안, 결정 수동 |
| 법령/판례 모니터링 | 분기 | 의안정보시스템/판례속보 확인 (수동) |
| 전체 사전 감사 (출처 생존, 커버리지 갭) | 분기 | 자동 리포트 + 수동 검토 |

## 7. 법적/윤리적 가드레일 (재확인)

- **수집 금지**: 악성 커뮤니티 직접 크롤링, robots.txt 차단 사이트, 나무위키 자동 수집.
- **저장 최소화**: 뉴스 본문 전체 저장 금지(메타데이터+발췌만), 혐오 원문 이미지 원본 보관 최소화(해시/임베딩 위주), 개인 식별 정보 비수집.
- **라이선스 전파 추적**: CC BY-SA 출처 사용분은 source 테이블에서 추적 — 사전 외부 공개/판매 시 SA 전파 의무 법무 검토.
- **비-permissive 자원 격리**: NC(UnSmile/나무위키)·ND·재배포 제한(AI Hub)·**라이선스 불명(Womad Kaggle, bad_word_list, KOLD 등)** 자원은 모두 별도 스토리지·평가 전용 플래그, 릴리스 아티팩트에 절대 미포함 — **불명은 NC와 동일하게 차단이 기본값** (빌드 게이트 0에서 `license_class` 검사로 강제).
