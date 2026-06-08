# 모델 카드 — 문맥 분류기 v1 (context_clf, numpy LR)

> "같은 단어가 위험한 의미로 쓰였는가"를 판별하는 1차 문맥 분류기.
> 동음이의어(운지/된장녀/한남 등) 매칭의 `context_score`(harmful 확신도) 산출용.
> 산출물: `models/context_clf.json` (희소 가중치 + 해시설정 + 버전).

## 1. 용도 / 위치

- docs/03 §2 단계3(문맥 분류) 1차 분류기. `ambiguity != 'unambiguous'` 매치에만 호출되어
  정책표의 `context_score`를 산출한다(unambiguous는 분류기 생략·1.0).
- `noise_checker.context_classifier.ContextClassifier.load(path).score(text, surface) ∈ [0,1]`.
- 엔진은 `NOISE_CONTEXT_MODEL` 환경변수 또는 `Engine.load(..., context_model=)` 경로로 로드.
  미탑재 시 `context_score`는 0.5로 폴백(M3 전 동작·하위호환).

## 2. 환경 제약과 단계화 (정직한 명시)

이 모델은 **임시 1차 분류기**다. 운영 환경(CPU 4코어·GPU 없음·torch/transformers 미설치)에서
docs/05 M3의 KcELECTRA→ONNX int8 풀 파인튜닝이 비현실적이라, 의존성 경량 **순수 numpy
로지스틱 회귀**로 대체했다. KcELECTRA→ONNX는 동일 인터페이스(load→score)를 유지한 채
**GPU 단계 과제로 남긴다** — 엔진은 인터페이스에만 의존하므로 교체 시 engine.py 변경 불필요.

## 3. 학습 데이터

- 출처: `data/context/contrastive-b{1..5}.jsonl` — 자체 구축 동음이의어 대조 셋.
  총 748행 / 29 surface, harmful 360 · benign 388 (surface별 위험·무해 용례 대조 쌍).
- subtype: direct(직접 비하 360) · homonym(동음이의 무해 193) · daily(일상 50) ·
  quotation(인용·메타 64) · counterspeech(대항표현 81).
- **license_class: 전량 `source=synth`(자체 작성 합성)** — 공개 NC 코퍼스(KOLD/UnSmile/K-MHaS 등)
  미사용. 따라서 **NC 라이선스 상용 제약 없음** (법무 검토 플래그 비해당). KcELECTRA 단계에서
  공개 코퍼스를 섞을 경우 NC 데이터 학습분의 상용 가능성은 별도 법무 검토 대상.
- surface당 ≥50쌍 목표(docs/05 M3): 일부 surface는 미달이라 KcELECTRA 단계 전 합성 보강 백로그.

## 4. 학습 방법 (결정적)

- 피처(순수 numpy): 문자 n-gram(2,3) 해싱 + 단어 unigram 해싱(해시 트릭 2^18) +
  surface 자체 해싱 + 보조 피처(메타담론·대항표현·직접비하 토큰, 따옴표 감쌈, surface 반복).
  학습·추론 피처는 `context_classifier.extract_features` 단일 정의 공유(서빙 불일치 방지).
- 모델: 클래스 가중(역빈도) L2 로지스틱 회귀, full-batch GD(seed 고정 결정적).
- 캘리브레이션: val 로짓에 온도 스케일(T) 적합(NLL 최소) — 확신도가 harmful 확률 의미를 갖도록.
- train/val 80/20 **surface별 층화분할**.

## 5. 평가 결과 (val, 149행)

| 지표 | train | val |
|---|---|---|
| accuracy | 1.000 | 0.873 |
| precision | 1.000 | 0.810 |
| recall | 1.000 | 0.941 |
| f1 | 1.000 | 0.871 |
| AUC | 1.000 | 0.951 |

- val F1 0.871 ≥ docs/05 M3 목표(0.85). train 1.0은 해시 n-gram LR의 과적합(예상) — val로 판단.
- 온도 T=0.900 (가중치+해시설정과 함께 JSON 저장).

### 골든셋 재채점 (context_score 0.5 고정 → 분류기) — 회귀 없음

| | 전(0.5 고정) | 후(분류기) |
|---|---|---|
| must_catch recall / sev5 | 1.00 / 1.00 | 1.00 / 1.00 |
| must_pass pass_rate | 1.00 | 1.00 |
| **ambiguous review 발생(분리 보고)** | **15** | **4** |
| evasion recall | 1.00 | 1.00 |
| 게이트 4종 | 전부 PASS | 전부 PASS |

핵심 효과: 무해 ambiguous(동음이의·인용·대항표현) 매치의 `context_score`가 하락해
review 발생이 15→4로 감소(F8/F19/F20 무해 용례 해소). 남은 4건은 **unambiguous** 용어
(맘충·전라디언·군무새)가 인용/대항표현에 등장한 경우로, 분류기 비대상이며 M2 인용 휴리스틱이
상한 review로 보존한다(정상).

## 6. 알려진 한계

- **"슬러 사용을 서술하는" 문장의 저평가**: must_catch의 harmful 중 일부(예: "…로 조롱하는 댓글",
  "…모욕하는 게시물")는 인용·대항표현과 어휘가 겹쳐 context_score가 0.5 미만으로 낮게 나온다
  (LR이 bag-of-ngram이라 "행위 서술 vs 메타 인용"을 못 가른다). 이 경우에도 **매칭 자체는 유지**되어
  must_catch recall은 영향 없으며(권고 등급만 하향), 대부분(13/14)이 경계 구간(0.4~0.6)에 들어
  `context_low_confidence` 플래그로 **2차 LLM 판정 대상**이 된다(아래 §7).
- 단일 도메인(합성 댓글체) 학습 → 도메인 시프트(뉴스 본문·구어 등)에 약함. KcELECTRA 단계에서 보강.
- pattern 매치('~노' 등)는 matched_text가 사용자 문장 전체라 surface 단독 신호가 약해 폴백 0.5 유지.
- surface별 표본 불균형(일부 <50쌍) → 표본 적은 surface의 확신도 신뢰 낮음.

## 7. 신뢰도 구간 / LLM 폴백 설계 (docs/03 §2 단계3)

- **high-conf**: context_score ≥ 0.85 → 자동 판정(ambiguous도 revise 캡 해제 가능).
- **mid(경계)**: 0.4 ≤ score ≤ 0.6 → `context_low_confidence` 플래그 부여 → **2차 LLM 판정 대상**.
  (이번 단계는 훅·플래그만 구현. 실제 Claude API 호출은 미구현 — claude-haiku-4-5 기본,
  경계 사례 claude-sonnet 단계화는 KcELECTRA 통합 시 결선.)
- **low(<0.4 무해 / >0.6 위험)**: 분류기 단독 판정. (운영 임계는 캘리브레이션 재검 후 조정.)

## 8. 버저닝

- 피처 스펙: `feature_version=ctx-feat-1` (모델 JSON과 코드 `FEATURE_VERSION` 대조 — 불일치 시 로드 거부).
- 데이터/모델 버전은 dictionary_release와 **독립 버저닝**(docs/05 M3) — 분기마다 신조어 반영 재학습.
- 재학습: `uv run python scripts/train_context_classifier.py`.
