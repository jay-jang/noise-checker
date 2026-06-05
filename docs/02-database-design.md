# 02. 데이터베이스 설계 — 혐오 용어/표식 사전 (Lexicon DB)

> 핵심 원칙: **모든 항목은 출처(source)와 유래(origin)를 반드시 가진다.**
> "이 단어가 왜 위험한가?"에 대해 검증 가능한 근거(URL, 인용)를 항상 제시할 수 있어야 한다.
> 근거 없는 항목은 `draft` 상태를 벗어날 수 없다.

## 1. 설계 목표

| 요구사항 | 설계 반영 |
|---|---|
| 단어·문구·패턴·이미지 표식을 모두 수용 | `term`(텍스트) + `image_marker`(이미지) 이원 구조 |
| 항목별 출처/유래 명시 | `source` 테이블 + N:M 증거 연결(`term_evidence`), `origin_*` 필드 |
| 변형(자모분리, 특수문자 삽입 등) 대응 | `term_variant` + 정규화 키(`normalized_key`) |
| 동음이의어 오탐 방지 (예: "운지"=버섯) | `ambiguity` 플래그 + `safe_context` 목록 → 문맥 분류로 라우팅 |
| 주기적 업데이트 + 사람 검수 | `status` 상태기계 + `review_log` 감사 추적 |
| 검사 서비스 배포 안정성 | `dictionary_release` 불변 스냅샷 버저닝 |
| 실사고 사례 축적 (테스트 겸용) | `incident` 테이블 |

## 2. ERD 개요

```
source ──< term_evidence >── term ──< term_variant
   │                          │  ├──< term_category (M:N → category)
   │                          │  ├──< composite_rule (조합/맥락 규칙)
   │                          └──< review_log
   ├──< marker_evidence >── image_marker ──< marker_reference_image
   │                          └──< review_log
   └──< incident >── (term | image_marker 참조)

dictionary_release ──< release_item (term/variant/marker/composite_rule 스냅샷)
```

## 3. 테이블 정의 (PostgreSQL)

### 3.1 `source` — 출처 원장

모든 근거 자료의 단일 원장. 동일 URL은 한 번만 등록하고 여러 항목이 참조한다.

```sql
CREATE TABLE source (
    id            BIGSERIAL PRIMARY KEY,
    url           TEXT UNIQUE,                  -- 원본 URL (오프라인 자료면 NULL 허용)
    title         TEXT NOT NULL,
    source_type   TEXT NOT NULL CHECK (source_type IN (
                    'dataset',      -- 공개 데이터셋 (KOLD, UnSmile 등)
                    'wiki',         -- 나무위키/위키백과
                    'news',         -- 언론 보도
                    'academic',     -- 학술 논문
                    'community',    -- 커뮤니티 원문(직접 인용은 최소화)
                    'government',   -- 공공기관 자료
                    'internal'      -- 자체 검수/리서치
                  )),
    publisher     TEXT,                         -- 매체/기관/저자
    published_at  DATE,
    retrieved_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    license       TEXT,                         -- 사람 가독용 원문 (예: 'CC BY-NC-SA 2.0 KR', 'MIT', '인용만 가능')
    license_class TEXT NOT NULL DEFAULT 'unknown' CHECK (license_class IN (
                    'permissive',     -- MIT/Apache/CC BY — 상업·재배포 확정
                    'share_alike',    -- CC BY-SA — 릴리스 가능하나 SA 전파 추적 필수
                    'noncommercial',  -- CC *-NC* — 릴리스 금지
                    'no_derivatives', -- *-ND — 릴리스 금지
                    'restricted',     -- AI Hub 등 자체약관·재배포 제한 — 릴리스 금지
                    'unknown'         -- 불명/미확정 — 확정 전까지 NC와 동일하게 차단
                  )),                            -- 게이트 판정은 free-text가 아닌 이 필드 기준
                                                 -- (원자료 표기 변이 'CC BY-SA' vs 'CC-BY-SA' 때문에 문자열 매칭 불가)
    reliability   SMALLINT NOT NULL DEFAULT 3   -- 1(낮음)~5(높음): 뉴스/학술=4-5, 위키=3, 커뮤니티=2
                  CHECK (reliability BETWEEN 1 AND 5),
    archive_url   TEXT,                         -- 웹아카이브 백업 (출처 소실 대비)
    snapshot_path TEXT,                         -- 수집 시점 본문 스냅샷 저장 경로 (S3 등)
    notes         TEXT
);
```

> **출처 소실 대비**: 나무위키 문서·뉴스 기사는 수정/삭제될 수 있으므로 수집 시점에
> `archive_url`(web.archive.org 등록) 또는 `snapshot_path`(본문 사본)를 반드시 채운다.

### 3.2 `term` — 텍스트 용어/문구

```sql
CREATE TABLE term (
    id              BIGSERIAL PRIMARY KEY,
    surface         TEXT NOT NULL,              -- 대표 표기 (예: '운지')
    normalized_key  TEXT NOT NULL,              -- 정규화 키 (자모분해+소문자+특수문자 제거)
    term_kind       TEXT NOT NULL CHECK (term_kind IN ('word','phrase','pattern','number')),
                    -- pattern: 정규식 항목(예: 특정 숫자조합), number: 상징 숫자
    origin_community TEXT,                      -- 유래 커뮤니티: 'ilbe','megalia','womad','dcinside', 'other', 'unknown'
    origin_story    TEXT NOT NULL,              -- 유래 설명 (언제/어떤 사건에서/어떤 의미로 생겼는지)
    origin_period   TEXT,                       -- 대략적 발생 시기 (예: '2012년경')
    meaning         TEXT NOT NULL,              -- 커뮤니티 내 사용 의미
    severity        SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5),
                    -- 5: 사용 즉시 중대 논란(고인비하 등), 3: 맥락상 위험, 1: 주의 관찰
    ambiguity       TEXT NOT NULL DEFAULT 'unambiguous' CHECK (ambiguity IN (
                      'unambiguous',  -- 일반 언어에서 거의 안 쓰임 → 매칭 즉시 플래그
                      'ambiguous',    -- 일반 단어와 동철 (예: 운지=버섯/낙하 비하) → 문맥 분류 필요
                      'common'        -- 일상어지만 특정 조합/맥락에서만 위험 → 조합 규칙 필요
                    )),
    safe_contexts   TEXT[],                     -- 무해 문맥 예시 키워드 (예: '{버섯,운지버섯,약초}')
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
                      'draft',        -- 수집됨, 근거 미확정
                      'watchlist',    -- 근거 약함·모니터링 가치 있음 (emerging — 교차 리뷰 합의 4):
                                      --   언론화 전 신조어의 중간 상태. 검사 응답에서 monitor 등급 고정,
                                      --   차단/수정 권고에 사용 금지. evidence 확보 시 in_review로 승격
                      'in_review',    -- 검수 중
                      'active',       -- 검사에 사용
                      'deprecated',   -- 더 이상 위험하지 않음(사어화) — 이력 보존
                      'rejected'      -- 오수집 판정
                    )),
    release_policy  TEXT NOT NULL DEFAULT 'general' CHECK (release_policy IN (
                      'general',         -- 전 고객 채널 배포 가능
                      'advisory_only',   -- 배포하되 등급 상한 review_recommended (도그휘슬·회색지대)
                      'internal_only',   -- 내부 도구 전용 — 고객 노출 아티팩트에서 제외
                      'hold_legal'       -- 법무 검토 통과 전 모든 릴리스에서 제외
                    )),                          -- status(검수 상태)와 직교하는 배포 정책 축 (교차 리뷰 합의 8)
    provenance_class TEXT NOT NULL DEFAULT 'internal' CHECK (provenance_class IN (
                      'permissive_core',     -- origin/definition evidence가 모두 permissive 또는 자체 작성
                      'share_alike_core',    -- SA 출처 파생 서술 포함 → origin_story 텍스트 응답 비노출 기본값
                      'restricted_eval_only',-- NC/ND/restricted/unknown 근거만 존재 → 릴리스 불가 (평가 전용)
                      'internal'             -- 자체 리서치·실사고 기반 (응답 노출 가능)
                    )),                          -- 라이선스 3계층 (교차 리뷰 합의 1). evidence 변경 시 빌드가 재계산·검증
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (normalized_key, term_kind)
);
CREATE INDEX idx_term_status ON term(status);
CREATE INDEX idx_term_nkey   ON term(normalized_key);
```

> **상태 기계**: `draft → in_review → active ↔ deprecated`, 어디서든 `→ rejected`.
> `watchlist`는 `draft ↔ watchlist → in_review` — active로 직접 전이 불가 (evidence 게이트 우회 방지).
> `active` 전이는 **근거(evidence) 1건 이상 + 검수자 승인**이 있어야만 가능.
> **강제 지점은 DB 트리거 단일**: `BEFORE INSERT OR UPDATE OF status` 트리거가 `NEW.status='active'`일 때
> `term_evidence`에 `evidence_type IN ('origin','definition')` 행 ≥ 1을 검사, 미충족 시 예외.
> (INSERT도 검사해야 직접 `INSERT ... status='active'` 우회를 막는다. 마지막 origin/definition evidence 삭제는
> status='active'인 동안 차단. 앱 레이어 검증은 UX용 조기 경고일 뿐 강제 책임이 없다.)

### 3.3 `term_evidence` — 용어↔출처 증거 연결 (유래의 핵심)

```sql
CREATE TABLE term_evidence (
    term_id     BIGINT NOT NULL REFERENCES term(id) ON DELETE CASCADE,
    source_id   BIGINT NOT NULL REFERENCES source(id),
    evidence_type TEXT NOT NULL CHECK (evidence_type IN (
                  'origin',       -- 유래를 설명하는 출처
                  'usage',        -- 실제 사용례를 보여주는 출처
                  'incident',     -- 이 용어로 인한 논란 보도
                  'definition'    -- 의미 정의 출처 (사전/데이터셋)
                )),
    excerpt     TEXT CHECK (char_length(excerpt) <= 300),
                                  -- 해당 출처에서의 관련 인용 — 최소 인용 원칙을 DB 제약으로 강제
                                  -- (수집기 버그로 본문 대량 복제가 적재되는 저작권 리스크 차단)
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    added_by    TEXT NOT NULL,    -- 수집 파이프라인 ID 또는 검수자
    PRIMARY KEY (term_id, source_id, evidence_type)
);
```

### 3.4 `term_variant` — 변형 표기

```sql
CREATE TABLE term_variant (
    id             BIGSERIAL PRIMARY KEY,
    term_id        BIGINT NOT NULL REFERENCES term(id) ON DELETE CASCADE,
    variant        TEXT NOT NULL,            -- 예: '운G', 'ㅇㅈ' (위험 변형만)
    variant_kind   TEXT NOT NULL CHECK (variant_kind IN (
                     'jamo',         -- 자모 분리 (ㅅㅂ)
                     'leet',         -- 숫자/기호 치환 (시1발)
                     'chosung',      -- 초성체
                     'yamin',        -- 야민정음 (머가리)
                     'translit',     -- 영문/외국어 음차
                     'spacing',      -- 띄어쓰기 변형
                     'regex'         -- 위 외 정규식으로만 표현 가능한 패턴
                   )),
    pattern        TEXT,                     -- variant_kind='regex'일 때 정규식
    normalized_key TEXT NOT NULL,
    auto_generated BOOLEAN NOT NULL DEFAULT false,  -- 규칙엔진 자동생성 여부
    verified       BOOLEAN NOT NULL DEFAULT false,  -- 검수자 확인 여부 (미확인 자동생성은 release 제외 가능)
    UNIQUE (term_id, variant)
);
```

### 3.5 `category` + `term_category` — 다중 분류

```sql
CREATE TABLE category (
    id    SERIAL PRIMARY KEY,
    code  TEXT UNIQUE NOT NULL,   -- 'region_hate'(지역비하), 'misogyny', 'misandry',
                                  -- 'deceased'(고인비하), 'disability', 'race_nation',
                                  -- 'politics', 'sexual_minority', 'community_jargon'(은어일반)
    label TEXT NOT NULL,
    description TEXT
);
CREATE TABLE term_category (
    term_id     BIGINT REFERENCES term(id) ON DELETE CASCADE,
    category_id INT REFERENCES category(id),
    PRIMARY KEY (term_id, category_id)
);
```

> 카테고리 코드는 공개 데이터셋(UnSmile, K-MHaS 등)의 라벨 체계와 매핑 테이블을 두어
> 데이터셋 융합 시 일관성을 유지한다 (`docs/01-research-report.md`의 라벨 매핑 표 참조).

### 3.6 `image_marker` — 이미지 표식

```sql
CREATE TABLE image_marker (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL,            -- 예: '일베 손모양', '메갈리아 로고'
    marker_kind     TEXT NOT NULL CHECK (marker_kind IN (
                      'hand_sign',    -- 손모양
                      'logo',         -- 커뮤니티 로고 및 변형
                      'meme_image',   -- 특정 짤방/합성 이미지 (고인 비하 합성 등)
                      'watermark',    -- 커뮤니티 워터마크
                      'symbol'        -- 기타 기호
                    )),
    origin_community TEXT,
    origin_story    TEXT NOT NULL,
    severity        SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5),
    detection_method TEXT[] NOT NULL,         -- '{phash,clip,hand_landmark,ocr,object_detection}'
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN
                      ('draft','watchlist','in_review','active','deprecated','rejected')),
                    -- term과 동일 상태기계 + 동일 active 게이트 트리거 (marker_evidence ≥ 1, origin/definition)
    release_policy  TEXT NOT NULL DEFAULT 'advisory_only' CHECK (release_policy IN
                      ('general','advisory_only','internal_only','hold_legal')),
                    -- term §3.2와 동일 축. 표식은 기본 advisory_only (도그휘슬 메타 리스크 — 손모양은 internal_only 권장)
    provenance_class TEXT NOT NULL DEFAULT 'internal' CHECK (provenance_class IN
                      ('permissive_core','share_alike_core','restricted_eval_only','internal')),
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE marker_reference_image (
    id          BIGSERIAL PRIMARY KEY,
    marker_id   BIGINT NOT NULL REFERENCES image_marker(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,               -- S3/로컬 경로 (레퍼런스 이미지 원본)
    phash       BIT(64),                      -- perceptual hash
    clip_embedding vector(512),               -- pgvector: CLIP 임베딩 (유사도 검색)
    source_id   BIGINT REFERENCES source(id), -- 이 레퍼런스 이미지의 출처
    license_ok  BOOLEAN NOT NULL DEFAULT false, -- 보관/사용 권리 확인 여부
    notes       TEXT
);

CREATE TABLE marker_evidence (                -- term_evidence와 동형
    marker_id   BIGINT NOT NULL REFERENCES image_marker(id) ON DELETE CASCADE,
    source_id   BIGINT NOT NULL REFERENCES source(id),
    evidence_type TEXT NOT NULL,
    excerpt     TEXT,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    added_by    TEXT NOT NULL,
    PRIMARY KEY (marker_id, source_id, evidence_type)
);
```

> `pgvector` 확장으로 CLIP 임베딩 유사도 검색을 DB에서 직접 수행 (소규모에선 충분, 수만 장 이상이면 FAISS 분리).

### 3.7 `incident` — 실사고 사례 (근거 + 회귀 테스트 셋)

```sql
CREATE TABLE incident (
    id          BIGSERIAL PRIMARY KEY,
    title       TEXT NOT NULL,                -- 내부용 원제목 (기업 실명 포함 가능, 예: '○○사 광고 일베 용어 논란 (2015)')
    display_title TEXT,                       -- 외부 노출용 일반화 제목 (예: '국내 편의점 광고 사례 (2021)')
    occurred_at DATE,
    description TEXT NOT NULL,                -- 무엇이 어떻게 문제가 됐는지
    medium      TEXT CHECK (medium IN ('ad','broadcast','game','product','sns','app','other')),
    term_id     BIGINT REFERENCES term(id),         -- 관련 용어 (둘 중 하나 이상)
    marker_id   BIGINT REFERENCES image_marker(id),
    source_id   BIGINT NOT NULL REFERENCES source(id),  -- 보도 출처
    sample_text TEXT,                         -- 문제가 된 실제 문구 (내부 전용 — 회귀 테스트에 사용, 최소 인용 원칙 적용)
    legal_reviewed BOOLEAN NOT NULL DEFAULT false,  -- 기업·개인 실명 노출에 대한 법무 검토 여부
    disclosable    BOOLEAN NOT NULL DEFAULT false,  -- API 노출 허용 (legal_reviewed=true 전제, display_title만 노출)
    CHECK (term_id IS NOT NULL OR marker_id IS NOT NULL)
);
```

> **incident 노출 거버넌스** (01 §5 '공연성 차단·기업 명단 금지'의 스키마 강제):
> API(`related_incidents`, `/v1/lexicon/terms/{id}`)는 `disclosable=true` 행의 `display_title`만 반환 —
> 원 `title`(기업 실명)과 `sample_text`는 절대 외부 노출 금지. 뉴스 수집기가 만드는 incident는
> 기본 `legal_reviewed=false, disclosable=false`로 적재되어 자동 노출이 불가능하다.

### 3.8 `composite_rule` — 조합/맥락 규칙 (숫자 코드, 동시 출현)

`ambiguity='common'`(특정 조합에서만 위험)과 `term_kind='number'`의 실제 판정 규칙 저장처.
"523은 단독으론 무해하지만 날짜/금액 맥락 또는 다른 일베 코드와 동시 출현 시 고위험" 같은 규칙을 모델링한다.

```sql
CREATE TABLE composite_rule (
    id              BIGSERIAL PRIMARY KEY,
    primary_term_id BIGINT NOT NULL REFERENCES term(id),   -- 예: '523' (number)
    trigger_kind    TEXT NOT NULL CHECK (trigger_kind IN (
                      'co_occurrence',  -- 다른 위험 term과 동시 출현
                      'date_context',   -- 날짜 표기 맥락 (5.23, 5월 23일)
                      'amount_context', -- 금액 맥락 (52,300원)
                      'time_context',   -- 시각 맥락 (17:23)
                      'proximity'       -- OCR 좌표 인접/겹침 (자막 레이어)
                    )),
    trigger_terms   BIGINT[],            -- co_occurrence일 때 대상 term id 배열
    trigger_pattern TEXT,                -- date/amount/time일 때 정규식 (예: '52,?300\s*원')
    proximity_window INT,                -- 결합 인정 거리 (문자 수 또는 OCR px)
    base_severity   SMALLINT NOT NULL,   -- 단독 출현 시 강도 (보통 1~2 = 미플래그/monitor)
    severity_delta  SMALLINT NOT NULL,   -- 조건 충족 시 가산 → 합산이 실효 severity
    status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN
                      ('draft','in_review','active','deprecated','rejected')),
    notes           TEXT
);
```

> 검사 엔진은 number/common 항목 매칭 시 composite_rule을 평가해 `composite_score`를 산출하고
> 위험도 공식에 반영한다 (`03-architecture.md` §2 단계2·단계4). 규칙도 term과 동일하게 evidence·검수를 거친다.

### 3.9 `review_log` — 검수 감사 추적

```sql
CREATE TABLE review_log (
    id          BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('term','image_marker','variant')),
    entity_id   BIGINT NOT NULL,
    action      TEXT NOT NULL,                -- 'created','approved','rejected','severity_changed',...
    old_value   JSONB,
    new_value   JSONB,
    reviewer    TEXT NOT NULL,                -- 'pipeline:namuwiki-crawler' | 'human:이메일'
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    rationale   TEXT
);
```

### 3.10 `dictionary_release` — 배포 스냅샷

검사 API는 DB를 직접 읽지 않고 **컴파일된 릴리스 아티팩트**를 로드한다.

```sql
CREATE TABLE dictionary_release (
    id           BIGSERIAL PRIMARY KEY,
    version      TEXT UNIQUE NOT NULL,        -- 'v2026.06.04-1' (CalVer)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    term_count   INT NOT NULL,
    variant_count INT NOT NULL,
    marker_count INT NOT NULL,
    artifact_path TEXT NOT NULL,              -- 컴파일 결과물 경로 (아래 참조)
    effective_license TEXT NOT NULL,          -- 아티팩트에 전파되는 최종 라이선스
                                              -- (SA 파생물 1건 이상 포함 시 'CC BY-SA 4.0', 아니면 자체 라이선스)
    changelog    TEXT,
    released_by  TEXT NOT NULL
);
```

**릴리스 아티팩트 구성** (빌드 단계에서 `active` 항목만 컴파일 — `release_policy='internal_only'`는 내부 채널 아티팩트에만, `'hold_legal'`은 전 채널 제외. `watchlist` 항목은 별도 `watchlist.json`으로 내부 채널 전용):
- `lexicon.json` — 전체 사전 (용어+변형+메타데이터+출처 요약). 항목별 `provenance_class` 포함 —
  `share_alike_core` 항목의 origin_story 텍스트는 검사 API가 응답에 직접 싣지 않는다 (03 §2 단계 4, 08 Q1)
- `automaton.pkl` — Aho-Corasick 오토마톤 (정규화 키 기준, 즉시 로드용)
- `patterns.json` — 정규식 패턴 목록 + composite_rule 컴파일본
- `phash_index.bin` / `clip_index.faiss` — 이미지 표식 인덱스
- `attribution.json` — **저작자 표시 매니페스트**: SA/BY 출처별 저작자·URL·라이선스 목록 자동 생성
  (origin_story 등이 위키백과·페미위키 CC BY-SA 본문에서 파생되므로 산출물에 표기 의무 전파)
- `manifest.json` — 버전, 카운트, 체크섬, `effective_license`, **`normalizer_code_version`**
  (src/normalizer.py 해시 — API 로드 시 자기 normalizer 버전과 불일치하면 로드 거부+경고)

## 4. 정규화 키 규약 (`normalized_key`)

검사 시 입력 텍스트와 사전 양쪽에 동일하게 적용하는 함수:

1. 유니코드 NFKC 정규화 (전각/호환 문자 통일)
2. 소문자화 (라틴)
3. 한글 음절 → 호환 자모 분해 (예: `운지` → `ㅇㅜㄴㅈㅣ`) — 자모 분리 변형과 동일 키로 수렴
4. 제로폭 문자·결합 기호 제거
5. 반복 문자 압축은 **하지 않음** (1차 매칭은 보수적으로, 변형은 `term_variant`로 명시 관리)
6. 특수문자 삽입 대응은 매칭 단계에서 skip-char 윈도우로 처리 (키 자체에서 제거하면 오탐 급증)

> 정규화 함수는 사전 빌드와 검사 API가 **같은 라이브러리 코드**를 import해야 한다 (버전 불일치 = 미탐).
> manifest의 `normalizer_code_version`으로 로드 시점에 강제 검증.

### 4.1 오프셋 매핑 — 자모 분해는 1→N 비가역이므로 명시적 추적 필수

검사 경로의 정규화는 문자열 하나가 아니라 튜플을 반환한다:

```python
normalize(text) -> (norm_text: str, src_offset: list[int])
# src_offset[i] = norm_text의 i번째 코드포인트가 유래한 원문 코드포인트 인덱스
```

- 단계 1~4의 **각 변환마다** 배열을 전파: 자모 분해(1→N)는 같은 원문 인덱스를 N회 반복,
  제로폭 삭제는 항목 제거, NFKC는 유니코드 매핑으로 추적.
- AC 매치 (자모 start, 자모 end)는 `src_offset`으로 원문 구간으로 환원한다.
- **음절 경계 스냅 규칙**: 매치 경계가 한 음절의 자모 중간을 가르는 부분 매치는 기본 **거부**
  (단, `variant_kind='jamo'`(ㅅㅂ)·`chosung`·`pattern` 항목은 자모/초성 단위 매칭이 정상이므로 예외).
  응답 span은 항상 원문 코드포인트(음절) 경계로 정렬됨을 보장.
- **불변식** (속성 테스트): `src_offset`은 단조 비감소이고 길이가 `norm_text`와 동일;
  모든 매치 m에 대해 `normalize(원문[m.span])[0] == 사전키[m.term]`.
- 사전 빌드 시 키 생성에는 offset이 필요 없으므로 `normalized_key`(§3.2)는 문자열 그대로 저장.

### 4.2 normalized_key 충돌 정책

NFKC/소문자화/자모 분해로 표면형이 다른 입력이 같은 키로 수렴하는 것은 **의도된 동작**이다
(자모 분리 변형을 한 키로 잡는 것이 목적). 별개 표면형이 같은 키와 충돌하면 등재 차단 오류가 아니라
기존 term의 `term_variant`로 통합한다. UNIQUE 키에 surface를 추가하지 말 것 — 수렴 자체가 깨진다.

## 5. 데이터 거버넌스

- **근거 없는 active 금지**: `active` **용어와 이미지 표식 모두** evidence ≥ 1 (그중 `origin` 또는 `definition` 타입 ≥ 1)을 DB 트리거로 강제 (§3.2/§3.6).
- **라이선스 게이트**: 릴리스 아티팩트에 컴파일되는 모든 active 항목은 연결된 evidence source 전부가 `license_class ∈ {permissive, share_alike}`여야 통과. **unknown/restricted는 NC와 동일하게 차단** (불명 = 차단이 안전 기본값). share_alike 포함 시 `effective_license`·`attribution.json`에 전파 기록.
- **라이선스 3계층 (provenance_class — 교차 리뷰 합의 1)**: 항목 단위로 `permissive_core` / `share_alike_core` / `restricted_eval_only`를 빌드가 evidence에서 재계산·검증. "상업 사용 가능 ≠ 폐쇄형 SaaS 응답 포함 가능" — `share_alike_core` 항목의 파생 서술은 법무 질의(docs/08 Q1) 회신 전까지 API 응답 비노출 기본값. 매칭·차단 동작 자체는 영향 없음(사실의 사용), 서술 텍스트만 통제.
- **배포 정책 분리 (release_policy)**: 검수 상태(status)와 별개로 항목별 배포 채널·등급 상한을 통제 (§3.2). `disclosable`(incident)·`hold_legal`(term)은 법무 검토 전 자동 노출이 구조적으로 불가능하게 한다.
- **반론 처리**: 오탐 신고(`/v1/feedback`)는 `review_log`에 적재 → 검수 큐로.
- **사어화 관리**: 12개월간 매칭/신고/뉴스 언급이 없는 용어는 분기 검수에서 `deprecated` 후보로 자동 제안.
- **저작권/법적 고려**: 커뮤니티 원문 장문 인용 금지(`excerpt`는 최소 인용), 레퍼런스 이미지는 `license_ok` 확인 후 보관.
- **법무 검토 플래그 범위**: ① term — 특정인 실명 기반 비하어, ② **incident — 기업·개인 실명(`title`) 및 `sample_text`의 외부 노출** (`disclosable=true` 전환은 법무 검토 필수, §3.7).
