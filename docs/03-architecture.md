# 03. 서비스 아키텍처 — Noise Checker

> 단어·문장·이미지를 입력받아 악성 커뮤니티 용어/표식 여부를 검사하고,
> **매칭 근거(출처·유래)와 권고**를 함께 반환하는 검사 서비스.

## 1. 전체 구성도

```
┌─────────────────────────────────────────────────────────────────┐
│                        수집계 (Update Pipeline)                   │
│  [스케줄러] → 수집기들(위키/뉴스/데이터셋/HF모델) → 후보 큐 → 검수 콘솔  │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     관리계 (Lexicon DB: PostgreSQL)               │
│   term / variant / image_marker / source / evidence / incident   │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼  (active 항목만 컴파일)
┌─────────────────────────────────────────────────────────────────┐
│              빌드계 (Dictionary Build & Release)                  │
│   정규화 → 변형 자동생성 → 골든셋 회귀검증 → 아티팩트 서명/배포        │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼  (릴리스 아티팩트 로드)
┌─────────────────────────────────────────────────────────────────┐
│                      검사계 (Detection API)                       │
│  ┌─ 텍스트 파이프라인 ──────────────────────────────┐              │
│  │ 정규화 → AC오토마톤 → 정규식/퍼지 → 문맥분류(ML/LLM)│              │
│  └──────────────────────────────────────────────┘              │
│  ┌─ 이미지 파이프라인 ──────────────────────────────┐              │
│  │ OCR→텍스트파이프 │ pHash/CLIP→표식매칭 │ 손모양감지 │              │
│  └──────────────────────────────────────────────┘              │
│            → 위험도 산정 → 근거(출처/유래) 첨부 → 응답               │
└─────────────────────────────────────────────────────────────────┘
```

네 개의 계(plane)는 독립 배포 가능. 검사계는 DB 장애와 무관하게 동작한다(아티팩트만 로드).

## 2. 텍스트 검사 파이프라인

### 단계 0 — 정규화 (+오프셋 배열)
DB 설계 문서 §4의 정규화를 적용하되, 검사 경로는 `normalize(text) -> (norm_text, src_offset)` 튜플을 사용 (02 §4.1). 자모 분해는 1→N 비가역 매핑이므로 변환 단계마다 per-character 오프셋 배열을 전파해야 원문 좌표 환원이 가능하다. 입력과 함께 **문장당 1회 Kiwi 형태소 분석**을 수행해 형태소 경계 인덱스를 미리 계산한다 (매치마다 호출하지 않음 — 호출 수가 매치 수 M이 아닌 입력 길이 N에 비례).

### 단계 1 — Aho-Corasick 다중 패턴 매칭
- AC 스캔 자체는 ~수십 µs. `active` 용어+검증된 변형의 정규화 키를 모두 담은 오토마톤 1회 스캔.
- **음절 경계 정렬 필터** (AC 직후, 형태소 검사 전): 자모 스트림 매치는 src_offset으로 환원했을 때 시작이 음절 초성 경계·끝이 음절 종성 경계에 정렬된 경우만 유효. 종성→다음 초성 이음새를 가로지르는 부분 매치(예: '원조/안주' 안의 ㄴ|ㅈ 이음새)는 폐기. 단 `variant_kind='jamo'`(ㅅㅂ)·`chosung`·`pattern` 항목은 자모 단위 매칭이 정상이므로 term_kind/variant_kind 기준으로 예외.
- **빠른 경로**: exact 매치 + `ambiguity='unambiguous'` + safe_contexts 비해당이면 형태소 검사·퍼지 생략.
- 잔여 후보만 미리 계산된 형태소 경계 인덱스 조회(문장당 1회 분석 결과 재사용)로 조사/어미 부착 확인 + `safe_contexts` 대조. 예: "운지버섯" 안의 "운지".

### 단계 2 — 패턴/퍼지/조합 매칭 (~ms)
- `term_kind='pattern'` 정규식 (특수 표기).
- **조합 규칙 평가 (composite_rule, 02 §3.8)**: number/common 항목은 단독으론 저강도. 날짜/금액/시각 맥락 정규식, 다른 위험 term과의 동시 출현, (이미지 경로에선) OCR 좌표 인접을 평가해 `composite_score` 산출 — "523 단독=무시, 5.23+17:23+52,300원 결합=고위험".
- 특수문자 삽입 변형: skip-char 윈도우 매칭 (예: "시1발" — 사전 키 사이 비한글 1~2자 허용). M2 구현은 음절 사이 구분자 run(≤2자) 제거 2차 뷰를 AC 재스캔하고 confidence 0.8·flag `skip_char`을 부여한다. **불변식: 공백을 포함한 결합 매치('삼 일 한' 류)는 ambiguity 무관 상한 `review_recommended`** — 일반 문장의 정상 공백 오탐을 보수적으로 막는다.
- 퍼지(soynlp 자모 Levenshtein)는 AC 후보에 한해 적용, **후보 수 상한 + 조기 종료** 규칙으로 비선형 폭증 방지.
- 결과마다 `match_confidence` 부여 (정확 일치 1.0, 퍼지 매칭 < 1.0).

### 단계 3 — 문맥 분류 (조건부, ~수십 ms)
다음 경우에만 실행 (비용 절약 + 지연 최소화):
- 매칭 용어의 `ambiguity != 'unambiguous'` → **문맥 분류기**가 해당 문장에서 위험 의미로 쓰였는지 판단
  - 1차: KcELECTRA 기반 파인튜닝 분류기 (자체 호스팅, 빠름)
  - 2차(선택): 신뢰도가 낮은 경계 사례만 LLM API(Claude)로 판정 — 근거 문장 생성 겸용
- 사전 매칭이 0건이어도 문장 전체가 혐오표현 분류기에서 고위험으로 분류되면 "사전 외 위험" 경고
  (→ 이 문장은 신조어 후보로 수집계에 피드백)

### 단계 4 — 위험도 산정 및 응답 조립

**등급 어휘는 자문형으로 통일** (§6 법적 포지셔닝의 직접 반영 — 교차 리뷰 2026-06-05 합의 3):
판정·지시로 읽히는 `block/warn/info`를 쓰지 않고 권고 수준만 표현한다.

| usage_recommendation | 의미 | (구 명칭) |
|---|---|---|
| `revise_recommended` | 수정 검토를 강하게 권고 | block |
| `review_recommended` | 내부 검토 권고 | warn |
| `monitor` | 참고·관찰 | info |

**위험도 정책표 v1** (교차 리뷰 합의 6 — `f(...)` 명시화. M0에서 코드·골든셋 채점과 함께 고정, 변경은 릴리스 노트 의무):

```
effective_severity = term.severity                  # composite는 base_severity+severity_delta (충족 시)
risk_score = (effective_severity/5) × match_confidence × context_score
  - match_confidence: exact 1.0 / verified variant 0.9 / skip-char 0.8 / chosung 변형 0.7 / fuzzy ≤ 0.7
  - context_score: unambiguous=1.0 (분류기 생략) / ambiguous는 분류기 harmful 확신도 (M3 전에는 0.5 고정)
```

| 조건 (위에서부터 첫 매칭 적용) | usage_recommendation |
|---|---|
| 도그휘슬·의도성 미입증 표식 (집게손가락 등, §6 회색지대) | **상한 `review_recommended` 고정** — revise 금지 |
| M2 인용 휴리스틱: 매치가 따옴표류로 감싸이거나 ±15자에 메타담론 토큰(표현·멸칭·용어·단어·혐오 표현·차별·비하·보도·보고서·강의·논문·기사·비판·사례·인용. '모욕' 제외)이 있음 | **상한 `review_recommended`** — severity 5 unambiguous(삼일한 등)도 캡. 매치 제거 아님(자문 포지셔닝). flag `quotation_heuristic`. M3 문맥분류 도입 전의 규칙 기반 보수 장치 |
| chosung 변형 매치(`variant_kind='chosung'`): 초성체는 본질 lossy(단독 키 모호) | match_confidence 0.7 + **상한 `review_recommended`** — revise 금지. flag `chosung_variant`. 적재는 초성 ≥3자·FP-safe(context_required)만(scripts/build_verified_variants) |
| `ambiguity != 'unambiguous'` AND (M3 전 또는 context_score < 0.85) | 상한 `review_recommended` |
| `status='watchlist'`(emerging, 02 §3.2) 또는 evidence_strength 낮음 | `monitor` 고정 — 차단/수정 권고에 사용 금지 |
| severity ≥ 4 AND risk_score ≥ 0.7 | `revise_recommended` |
| risk_score ≥ 0.35 | `review_recommended` |
| 그 외 매칭 (composite 미충족 number/common 포함) | `monitor` |

`overall_recommendation` = 매칭들의 최고 등급. 불변식: ① ambiguous 항목은 문맥 분류기 확신 없이 revise 불가 ② watchlist는 어떤 경우에도 monitor ③ 등급 산정 입력값(`harm_likelihood`, `evidence_strength` 등)은 응답에 분리 노출해 고객이 자체 정책을 세울 수 있게 한다.

응답에는 매칭별로: 원문 위치, 매칭 형태, 대표 용어, 카테고리, 유래(아래 SA 정책 적용), 출처 링크 목록, 유사 실사고 사례(`disclosable=true`인 incident의 `display_title`만 — 02 §3.7 노출 거버넌스), 권고 문구(자문형 템플릿).

> **SA 파생 텍스트 응답 포함 금지 (기본값)**: `origin.summary` 등 유래 서술은 해당 term의
> `provenance_class='share_alike_core'`(02 §3.2)이면 응답에 **직접 포함하지 않는다** — 출처 링크와
> 메타데이터(커뮤니티/시기)만 반환. 법무 질의(08 문서 Q1) 회신 후 정책 재결정. permissive/자체 작성
> 유래만 `summary` 텍스트로 노출.

## 3. 이미지 검사 파이프라인

세 갈래를 병렬 실행 후 결과 병합:

| 갈래 | 대상 | 기술 | 비고 |
|---|---|---|---|
| **OCR → 텍스트 검사** | 이미지 내 문구 | PaddleOCR(한국어) 또는 클라우드 OCR → §2 파이프라인 재사용. **텍스트+좌표를 함께 추출**해 인접/겹침 텍스트 결합 검사 (예: '노진혁'+'무한 박수' 겹침 → '노무한 박수') | 가장 흔한 사고 경로(짤방 속 텍스트, 자막 겹침) |
| **표식 매칭** | 로고/짤방/워터마크 | pHash(정확·변형 적은 복제) + CLIP 임베딩 kNN(크롭/색변형 대응) | 임계값 이중화: pHash 해밍거리 ≤ 8 즉시 플래그, CLIP cos ≥ 0.92 warn |
| **손모양 감지** | 일베식 손모양 등 | MediaPipe Hands → 랜드마크 → 경량 분류기 | 오탐 높음 → 단독으로는 `review_recommended`까지만 + `requires_human_visual_review` 플래그, 사람 검토 권장 표시 |

- 합성 이미지(고인 비하 합성 등)는 pHash로 원본 변형 추적 + CLIP으로 의미 유사도.
- 이미지 파이프라인은 **비동기 워커**(큐 기반)로 처리, 텍스트는 동기 응답.

## 4. API 설계 (v1)

```
POST /v1/check/text        { text, options? }            → 동기, p95 < 150ms (문맥분류 시 < 500ms)
POST /v1/check/image       { image_url | base64 }        → 202 + job_id (비동기)
GET  /v1/jobs/{job_id}                                   → 이미지 검사 결과
POST /v1/check/batch       { items: [...] }              → 대량 검사 (마케팅 카피 일괄)
POST /v1/feedback          { check_id, verdict, note }   → 오탐/미탐 신고 → 검수 큐
GET  /v1/lexicon/terms/{id}                              → 용어 상세 (유래, 출처. 사례는 disclosable=true의
                                                            display_title만 — 기업 실명·sample_text 노출 금지)
GET  /v1/releases/current                                → 현재 사전 버전 (감사용)
```

### 응답 예시 (`/v1/check/text`)
```json
{
  "check_id": "chk_01HX...",
  "release_version": "v2026.06.04-1",
  "overall_recommendation": "revise_recommended",
  "usage_notice": "본 결과는 리스크 자문 의견이며 사실 판정이 아닙니다. 특정인에 대한 의도 추정·인사 조치의 근거로 사용하지 마십시오. 최종 판단과 책임은 이용 고객에게 있습니다.",
  "matches": [
    {
      "span": { "start": 12, "end": 14, "surface_in_text": "운지" },
      "term": "운지",
      "matched_variant": null,
      "categories": ["deceased", "community_jargon"],
      "harm_likelihood": 0.94,
      "controversy_likelihood": 0.97,
      "evidence_strength": "high",
      "ambiguity": "ambiguous",
      "context_verdict": { "label": "risk_context_detected", "score": 0.94, "model": "kcelectra-ft-v3" },
      "usage_recommendation": "revise_recommended",
      "origin": {
        "community": "ilbe",
        "period": "2011년경",
        "summary": "고(故) 노무현 전 대통령 서거 조롱 표현에서 유래… (provenance_class가 permissive/internal인 경우에만 텍스트 제공 — SA 파생이면 null + sources만)",
        "sources": [
          { "title": "…", "url": "https://...", "type": "news", "reliability": 4 }
        ]
      },
      "related_incidents": [ { "display_title": "국내 편의점 광고 사례 (2021)", "url": "https://..." } ],
      "recommendation": "내부 검토 후 '낙하' 등 대체 표현 사용을 고려하세요."
    }
  ],
  "out_of_lexicon_warning": null
}
```

- `harm_likelihood`(맥락상 위해 가능성)·`controversy_likelihood`(논란 재현 가능성)·`evidence_strength`(근거 강도: high/medium/low)는 분리 노출 — 도그휘슬류는 "혐오 여부"가 아니라 "논란 가능성" 모델이므로 `controversy_likelihood`만 높고 `harm_likelihood`는 낮을 수 있다.
- `usage_notice`는 모든 응답에 강제 포함 (생략 불가 필드 — §6 인사조치 활용 금지 고지).
- `recommendation` 템플릿은 자문형 동사만 허용 ("고려하세요", "검토를 권고합니다") — "제거하세요", "~입니다" 단정형은 템플릿 금지어.

## 5. 기술 스택

| 영역 | 선택 | 이유 |
|---|---|---|
| 검사 API | **Python 3.12 + FastAPI** | ML 생태계 통합, 비동기 지원 |
| 다중 패턴 매칭 | **pyahocorasick** (C 확장) | 수만 패턴 µs 단위 스캔 |
| 형태소/경계 검사 | **Kiwi (kiwipiepy)** | 신조어 강건성, 속도, 사용자 사전 |
| 문맥 분류 | **KcELECTRA 파인튜닝 → ONNX Runtime** | 댓글체 코퍼스 사전학습, CPU 서빙 가능 |
| LLM 폴백/근거 생성 | **Claude API (claude-haiku-4-5 기본, 경계사례 claude-sonnet-4-6)** | 비용-정확도 단계화 |
| OCR | **PaddleOCR(자체)** 또는 CLOVA OCR(정확도 필요 시) | 한국어 인식률 |
| 이미지 임베딩 | **OpenCLIP ViT-B/32** + pgvector(소규모)/FAISS(대규모) | 변형 강건 유사도 |
| 손모양 | **MediaPipe Hands** + scikit-learn 분류기 | 경량, 실시간 |
| DB | **PostgreSQL 16 + pgvector** | 단일 원장 + 벡터 검색 |
| 큐/캐시 | **Redis** (이미지 잡 큐 + 결과 캐시) | 단순성 |
| 수집 파이프라인 | **Python + APScheduler/cron**, 추후 Airflow | MVP는 단순하게 |
| 검수 콘솔 | **Next.js + 관리 API** (MVP: Streamlit) | 검수 효율 |
| 배포 | **Docker Compose → (확장 시) k8s** | 단계적 |

## 6. 법적 포지셔닝이 강제하는 제품 설계 (01 보고서 §5 근거)

- **자문(advisory), 판정(adjudication) 아님**: 모든 산출물은 "리스크 확률·의견 + 근거"로 표현. 등급 어휘 자체가 권고형(`revise_recommended`/`review_recommended`/`monitor` — §2 단계 4). "일베 표현이다" 같은 단정 문구는 응답 템플릿 금지어.
- **2차 피해 방지 고지 강제**: 모든 검사 응답에 `usage_notice`(의도 추정·인사 조치 근거 사용 금지) 포함 — 검출기 존재가 부당 징계를 가속하는 메타 리스크 대응 (교차 리뷰 합의 3). 약관에도 동일 사용 제한 조항.
- **SA 파생 서술 비노출 기본값**: `provenance_class='share_alike_core'`인 유래 서술은 법무 질의(docs/08 Q1) 회신 전까지 응답에 직접 포함하지 않는다 (§2 단계 4).
- **공연성 차단**: 검사 결과는 요청한 고객에게만 반환. 공개 랭킹, 기업 명단, 제3자 공유 기능은 만들지 않는다.
- **외부 신고 기능 미제공**: 신고 판단·실행은 고객 귀속 (무고죄 리스크 차단).
- **근거 보존 = 면책 자산**: 매칭 로그·사전 버전·출처 체인은 '진실 확신의 합리성' 입증 자료 — release_version과 evidence 체계가 법무 요구사항이기도 함.
- **회색지대(부인 가능성 높은 도그휘슬)**: 집게손가락처럼 의도성 미입증 표식은 `revise_recommended` 금지, 상한 `review_recommended` + 유래·반론 맥락 병기 (위키백과 '음모론' 서술 관점 반영 — §2 단계 4 정책표 첫 행으로 강제).
- 약관: 자문 정의 + 경과실 배상 상한 + 오탐 가능성·인간 검수 권고 명시 (약관규제법 §7 — 고의·중과실 면책 불가 전제).

## 7. 비기능 요구사항

- **지연**: 텍스트 동기 p95 150ms(문맥분류 제외) / 500ms(포함) — **조건 명시: 입력 ≤ 500자, 매치 ≤ 10건 기준** (다중 매치 긴 카피는 부하 테스트로 별도 측정). Kiwi는 문장당 1회 + 인스턴스 풀 재사용으로 콜드스타트 회피. batch API는 항목당 타임아웃 + 전체 데드라인 + 부분 결과 반환 정책을 별도 정의. 이미지 비동기 p95 10s.
- **사전 핫리로드**: 새 릴리스 아티팩트를 무중단 스왑 (이중 버퍼 로드 → 원자적 포인터 교체). **각 요청은 진입 시 현재 릴리스 포인터를 1회 캡처**하고 정규화·매칭·이미지 인덱스·응답 `release_version` 전 구간이 동일 스냅샷을 참조한다 (처리 중 스왑이 일어나도 진행 중 요청은 캡처 버전을 끝까지 사용). 로드 시 manifest의 `normalizer_code_version`이 API의 normalizer 버전과 불일치하면 로드 거부+경고. (다중 레플리카 확장 시 '전 레플리카 로드 완료 후 일괄 전환'은 k8s 단계의 향후 과제.)
- **감사 가능성**: 모든 응답에 `release_version` 포함 — "그때 왜 안 잡혔나"를 버전으로 재현 가능.
- **프라이버시**: 검사 입력 텍스트/이미지는 기본 24h 후 파기(고객 옵트인 시 미탐 분석용 보존), 로그에 원문 미기록(해시만).
- **악용 방지**: 이 서비스는 검출 회피 도구로 역이용될 수 있음 — API 키 발급제, rate limit, 변형 생성 규칙 비공개.
