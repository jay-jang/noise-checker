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
   │                          │  └──< term_category (M:N → category)
   │                          └──< review_log
   ├──< marker_evidence >── image_marker ──< marker_reference_image
   │                          └──< review_log
   └──< incident >── (term | image_marker 참조)

dictionary_release ──< release_item (term/variant/marker 스냅샷)
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
    license       TEXT,                         -- 예: 'CC BY-NC-SA 2.0 KR', 'MIT', '인용만 가능'
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
                      'in_review',    -- 검수 중
                      'active',       -- 검사에 사용
                      'deprecated',   -- 더 이상 위험하지 않음(사어화) — 이력 보존
                      'rejected'      -- 오수집 판정
                    )),
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (normalized_key, term_kind)
);
CREATE INDEX idx_term_status ON term(status);
CREATE INDEX idx_term_nkey   ON term(normalized_key);
```

> **상태 기계**: `draft → in_review → active ↔ deprecated`, 어디서든 `→ rejected`.
> `active` 전이는 **근거(evidence) 1건 이상 + 검수자 승인**이 있어야만 가능 (트리거 또는 앱 레이어에서 강제).

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
    excerpt     TEXT,             -- 해당 출처에서의 관련 인용 (저작권 고려, 짧게)
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
    status          TEXT NOT NULL DEFAULT 'draft',  -- term과 동일 상태기계
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
    title       TEXT NOT NULL,                -- 예: '○○사 광고 일베 용어 논란 (2015)'
    occurred_at DATE,
    description TEXT NOT NULL,                -- 무엇이 어떻게 문제가 됐는지
    medium      TEXT CHECK (medium IN ('ad','broadcast','game','product','sns','app','other')),
    term_id     BIGINT REFERENCES term(id),         -- 관련 용어 (둘 중 하나 이상)
    marker_id   BIGINT REFERENCES image_marker(id),
    source_id   BIGINT NOT NULL REFERENCES source(id),  -- 보도 출처
    sample_text TEXT,                         -- 문제가 된 실제 문구 (회귀 테스트에 사용)
    CHECK (term_id IS NOT NULL OR marker_id IS NOT NULL)
);
```

### 3.8 `review_log` — 검수 감사 추적

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

### 3.9 `dictionary_release` — 배포 스냅샷

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
    changelog    TEXT,
    released_by  TEXT NOT NULL
);
```

**릴리스 아티팩트 구성** (빌드 단계에서 `active` 항목만 컴파일):
- `lexicon.json` — 전체 사전 (용어+변형+메타데이터+출처 요약)
- `automaton.pkl` — Aho-Corasick 오토마톤 (정규화 키 기준, 즉시 로드용)
- `patterns.json` — 정규식 패턴 목록
- `phash_index.bin` / `clip_index.faiss` — 이미지 표식 인덱스
- `manifest.json` — 버전, 카운트, 체크섬

## 4. 정규화 키 규약 (`normalized_key`)

검사 시 입력 텍스트와 사전 양쪽에 동일하게 적용하는 함수:

1. 유니코드 NFKC 정규화 (전각/호환 문자 통일)
2. 소문자화 (라틴)
3. 한글 음절 → 호환 자모 분해 (예: `운지` → `ㅇㅜㄴㅈㅣ`) — 자모 분리 변형과 동일 키로 수렴
4. 제로폭 문자·결합 기호 제거
5. 반복 문자 압축은 **하지 않음** (1차 매칭은 보수적으로, 변형은 `term_variant`로 명시 관리)
6. 특수문자 삽입 대응은 매칭 단계에서 skip-char 윈도우로 처리 (키 자체에서 제거하면 오탐 급증)

> 정규화 함수는 사전 빌드와 검사 API가 **같은 라이브러리 코드**를 import해야 한다 (버전 불일치 = 미탐).

## 5. 데이터 거버넌스

- **근거 없는 active 금지**: `active` 용어는 `term_evidence` ≥ 1 (그중 `origin` 또는 `definition` 타입 ≥ 1) 강제.
- **반론 처리**: 오탐 신고(`/v1/feedback`)는 `review_log`에 적재 → 검수 큐로.
- **사어화 관리**: 12개월간 매칭/신고/뉴스 언급이 없는 용어는 분기 검수에서 `deprecated` 후보로 자동 제안.
- **저작권/법적 고려**: 커뮤니티 원문 장문 인용 금지(`excerpt`는 최소 인용), 나무위키 인용 시 CC BY-NC-SA 라이선스 표기, 레퍼런스 이미지는 `license_ok` 확인 후 보관.
- **개인정보**: 특정인 실명 기반 비하어는 명예훼손 리스크 검토 후 등재 (법무 검토 플래그).
