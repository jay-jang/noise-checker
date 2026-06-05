# 3-AI 교차 리뷰 종합 결론 — 2026-06-05

## 0. 프로세스

| 단계 | 내용 | 산출물 |
|---|---|---|
| 독립 리뷰 | Claude(Opus 4.8 서브에이전트), Codex(codex-cli 0.137.0), Antigravity(agy 1.0.5)가 동일 문서(README, docs/01~06, review-2026-06-04)를 서로 격리된 상태에서 리뷰 | `claude-review-2026-06-05.md` (C3/M9/m5), `codex-review-2026-06-05.md` (C4/M14/m6), `agy-review-2026-06-05.md` (C2/M6/m2) |
| 상호 리뷰 | 각 AI가 나머지 두 리뷰의 Critical/Major를 agree/partial/reject 판정 (문서 근거 필수) | `cross-verdicts-2026-06-05-{claude,codex,agy}.md` |
| 종합 | 본 문서 — 합의/쟁점/기각 정리 및 실행 결론 | (이 파일) |

발견 인용 표기: A=Claude, B=Codex, C=Antigravity. 예: A-C1 = Claude 리뷰의 Critical 1.

## 1. 합의 사항 (2개 이상 리뷰 독립 지적 + 상호 리뷰에서 생존)

우선순위 순. ★ = 3개 리뷰 모두 독립적으로 지적.

### ★ 합의 1. CC BY-SA 전파 경계 미정의가 사업모델을 위협 (A-C1, A-M2, B-C4, B-M10, C와 합의)
- origin_story의 청정 출처가 사실상 전부 SA 계열(위키백과/페미위키)이라 `effective_license`가 SA로 수렴하는데, **API 응답에 유래 요약을 싣는 행위가 SA "배포"에 해당하는지** — 고객사로의 의무 전가 여부 — 가 미분석. 모델 가중치로의 전이도 동일 축.
- 합의 처방: 데이터 3계층 분리(`clean_permissive_core` / `share_alike_core` / `restricted_eval_only`) + SA 파생 origin_story를 응답에 직접 포함하지 않는 정책 + 항목 단위 provenance 플래그. **법무 검토를 M0/M1 게이트로 승격.**

### ★ 합의 2. 검수 체계가 임계경로인데 도구·독립성 설계가 부족 — 검수 콘솔 M5→M0/M1 전진 (A-C3, B-C2, B-M12, C-M6)
- M1(300+ 검수)이 전체 임계경로인데 검수 콘솔이 M5에 배치 — 가장 검수량이 많은 구간을 맨손으로 통과하는 모순. 1인 운영의 "세션 분리"는 독립 판단 효과가 없고, IAA(검수자 간 일치도) 미측정, 검수자 심리 부담 대책 0줄.
- 상호 리뷰에서 Codex·agy 모두 **Critical 상향** 권고. M1 수량도 "active 300+" 대신 "실사고 기반 고위험 50~100 + must_pass 세트" 우선으로 재정의 권고(B-C2, Claude partial 동의).

### ★ 합의 3. 자문형 포지셔닝과 출력 언어의 직접 모순 (B-C1, B-M7, A-M4, C-M8)
- 03 응답 예시의 `overall_risk: "block"`, "제거하거나 교체하세요"는 03 §6 "판정 아님" 원칙과 정면 충돌. 이미지 표식(집게손가락)은 검출기 존재 자체가 부당 인사조치를 가속하는 메타 리스크 — 응답에 "인사조치 활용 금지" 고지 강제 누락.
- 합의 처방: `block/warn/info` → 권고형 어휘(`revise_recommended` 등)로 전환, `harm_likelihood`/`controversy_likelihood`/`evidence_strength` 분리, 사용 제한 고지를 응답 스키마에 강제. **스키마/API 계약에 박히므로 M0 전 결정 필수.**

### ★ 합의 4. 사전 중심 파이프라인과 최다 사고 유형(신규 도그휘슬)의 구조적 미스매치 (A-C2, B-M4, B-M5↘, C-C2)
- 신조어는 먼저 쓰이고 나중에 언론화 — evidence가 모이면 이미 사고 이후. 사전 매칭은 정의상 후행적.
- 합의 처방: `emerging_watchlist` 중간 상태 신설(차단 권고에 쓰지 않는 약한 신호), 제품 메시지를 "완전 차단"이 아니라 "근거 있는 고위험 코드 + 빠른 등재·검토 루프"로 정직하게 설정.

### ★ 합의 5. 문맥 분류기(KcELECTRA) 계획의 3중 리스크 (A-M2, A-M7, B-M10, C-M3)
- ① 2022 토크나이저의 2024~26 신조어 분절 한계 ② 라벨 체계가 다른 이종 데이터셋 병합 ③ 용어당 50쌍 학습의 과적합. 거기에 SA 학습 데이터의 가중치 전이 불확실성.
- 합의 처방: 초기 모델은 "최종 판정기"가 아니라 **ambiguous reranker로 역할 제한**. agy의 "LLM few-shot 우선" 대안은 Codex가 지연·비용·감사성 리스크로 신중론 — 절충: M3 초기 LLM few-shot 병행 평가 후 데이터 축적 시 전환.

### 합의 6. 위험도 공식 `f(...)` 미정의 (A-M1 — Codex가 Critical 상향 권고)
- `risk = f(severity, match_confidence, ...)`의 실제 매핑이 없어 M2 게이트(must_pass 98%)의 채점 자체가 재현 불가. 합의 3(출력 어휘)과 함께 묶어 M0에서 위험도 정책표를 먼저 고정해야 함.

### 합의 7. M2는 외부 MVP가 아니라 내부 알파 (B-M1, agy 합의, Claude partial)
- 문맥 분류 없는 M2는 동음이의어 warn 남발로 외부 신뢰를 깎음. "internal advisory alpha"로 명명하고 safe_contexts 기반 하드 필터를 M2에 포함(이미 계획된 1차 오탐 필터를 게이트로 격상).

### 합의 8. 릴리스 정책 메타데이터 부재 (B-M8, Claude 동의)
- `status=active` 일괄 컴파일은 텍스트/이미지 전용·고객군 민감도·법무 검토 여부를 구분 못함. `release_policy` 필드 추가 — **M0 스키마에 직접 영향.**

### 기타 생존 항목 (단일 리뷰지만 상호 리뷰에서 동의 획득)
- A-M3: 동기 경로의 외부 LLM 폴백 — 타임아웃/실패 시 등급 정책 필요 (Codex·agy 동의)
- A-M8: KOLD(라이선스 불명)가 06 벤치마크에 등장 — 격리 일관성 허점 (agy 동의, Codex partial)
- A-M9: "반복 문자 압축 안 함" 정규화와 한글 음절 삽입 회피의 충돌 — evasion 셋 실측 필요 (B-M3와 합의)
- B-M9: incident sample_text의 저장소/CI 노출 — 골든셋 공개/비공개 분리 (Claude·agy 동의)
- B-M13: v1 리뷰 #12의 candidate 단계 composite_rule 구조 미반영 — 실제 갭 (agy 동의; agy 자신의 "18건 전부 반영" 단정과 모순 → agy 과신 적발)
- C-M7: 핫리로드 이중 버퍼 OOM — 단, Rust 사이드카는 과처방, 메모리 예산 명시가 우선 (Codex partial)
- C-발견4: 텍스트(동기)/이미지(비동기) 분리로 캠페인 단위 통합 검사 UX 부재 (Codex partial — `/v1/check/campaign` 검토)
- C-발견10: `excerpt` 길이의 DB 제약 부재 — 저작권 리스크 (간단, M0에서 처리)

## 2. 쟁점 판정 (리뷰어 간 불일치 → 해소)

| 쟁점 | 판정 분포 | 결론 |
|---|---|---|
| **B-M5** 뉴스 신호원 편향 | Claude 동의 / agy **기각**(04 §1~2에 이미 6채널+signal_score 설계 존재 — 오독) | **부분 기각.** 다채널 설계는 이미 있음. 다만 "뉴스=실사고 evidence이지 선행 신호 아님"이라는 캘리브레이션 지적만 채택 |
| **B-M14** v1 #17(evasion 소유권) 미반영 | Claude **기각**(.claude/agents 프로필에 반영 확인 — Codex는 입력에서 프로필 누락) / agy 동의(06 본문에는 없음) | **기각하되 후속 조치.** 에이전트 프로필엔 있으나 06 본문에 없어 혼동 유발 — 06에 명시 한 줄 추가 |
| **C-C1** Kiwi 실패 시 매칭 무력화 (Critical) | Claude·Codex 모두 **강등**(1차 AC는 정규화 자모 키 기반, Kiwi는 보조 — 채택 설계를 결함으로 오독) | **Critical→Minor 강등.** 단, "active 용어의 Kiwi 사용자 사전 자동 등록" 제안은 채택 |
| **C-M5** 라이선스 게이트로 커버리지 붕괴 → Clean Room 필요 | Claude·Codex 모두 기각(01 §1.A·§7에 이미 채택된 전략의 재진술, "붕괴"는 과장) | **기각.** 단, Clean Room 절차를 SOP 문서로 명문화하는 가치는 인정(Codex Minor 4와 합치) |
| **A-M6** 베타 멀티 레플리카 버전 불일치 | agy 동의 / Codex 부분동의("VM 2대=API 2대" 단정 불가) | **약한 채택.** 버전 고정 조회·혼재 윈도우 명시만 백로그로 |
| **C-발견9** M2 "block만 실패" 채점은 꼼수 | Claude 기각(의도된 단계적 게이트 설계의 오독) | **기각.** 단, M2 safe_contexts 하드 필터 강화(합의 7)로 실질 우려는 해소 |

## 3. 기각 목록 (반영하지 않음)

- C-C1의 Critical 등급 (Kiwi 1차 의존 오독 — Minor로만 유지)
- C-M5 (Clean Room — 기존 전략 재진술)
- C-발견9 (M2 채점 규칙 — 의도된 설계)
- B-M5의 본체 (다채널 설계 기존재 — 캘리브레이션 문구만 채택)
- B-M14의 본체 (에이전트 프로필에 반영 기존재 — 06 명시화만)
- agy Part 1의 "v1 18건 전부 완벽 반영" 단정 (B-M13이 반례 — 교차 검증의 가치 입증)

## 4. 심각도 재조정 확정

| 항목 | 원래 | 조정 | 근거 |
|---|---|---|---|
| 검수 콘솔 전진 배치 (B-M12/C-M6) | Major | **Critical** | Codex·agy 일치 권고, 임계경로 직결 |
| 위험도 공식 미정의 (A-M1) | Major | **Critical** | Codex 권고 — 테스트 게이트·UX·법적 포지셔닝 전체를 막음 |
| Kiwi 의존 (C-C1) | Critical | **Minor** | Claude·Codex 일치 — 오독 |
| 프라이버시 vs 학습 충돌 (B-M6) | Major | **Minor** | agy 권고 — 24h 파기 원칙은 수호, 비식별 패킷 보강으로 충분 |

## 5. 실행 결론 — 마일스톤 반영안

### M0 시작 전 결정 (스키마·API 계약에 박히는 것 — 지금 안 하면 비쌈)
1. **출력 어휘 체계 확정**: `block/warn/info` → 자문형(`revise_recommended`/`review_recommended`/`monitor`) + `harm_likelihood`/`controversy_likelihood`/`evidence_strength`/`ambiguity_level` 분리 + 인사조치 활용 금지 고지 필드 (합의 3, Minor 2)
2. **위험도 정책표 v1**: `f(...)`의 실제 매핑 테이블 문서화 (합의 6)
3. **스키마 추가**: `term.release_policy`(합의 8), `emerging_watchlist` 상태(합의 4), license 3계층 플래그(합의 1), `excerpt` 길이 제약, candidate payload의 `proposed_composite_rules` 구조(B-M13)
4. **라이선스 법무 질의서 작성**: "SA 파생 origin 요약의 API 응답 포함 = 배포인가" — 답 나올 때까지 SA 파생 문장의 응답 직접 포함 금지를 기본값으로 (합의 1)

### M1 계획 수정
5. 검수 콘솔 MVP를 M1 첫 주로 전진 (후보 큐·evidence 첨부·라이선스 게이트 프리뷰·체크리스트) (합의 2)
6. M1 출시 기준 재정의: "active 300+" → "실사고 기반 고위험 50~100 active + must_pass 세트 + 운영 루프 가동" / 나머지는 draft 백로그 (합의 2)
7. IAA 측정 절차 + 검수자 부담 완화(노출 시간 상한 등) 명문화 (A-C3)
8. active 용어의 Kiwi 사용자 사전 자동 등록을 릴리스 빌더에 포함 (C-C1 잔존 가치)

### M2~M4 계획 수정
9. M2 명칭을 "internal advisory alpha"로 — 외부 파일럿은 safe_contexts 하드 필터 + 경량 문맥 규칙 이후 (합의 7)
10. M3 문맥 분류기는 ambiguous reranker로 역할 제한, LLM few-shot 병행 평가 (합의 5)
11. M4를 "OCR 트랙(제품)"과 "표식 리서치 트랙(내부)"으로 분리 — 손모양은 API 자동 경고 금지, `requires_human_visual_review`만 (합의 3·B-C3)

### 백로그 (방향 유지, 추후)
- 동기 경로 LLM 폴백의 타임아웃/실패 정책 (A-M3) / KOLD 평가 격리 명시 (A-M8) / evasion 셋 한글 음절 삽입 실측 (A-M9) / 골든셋 공개·비공개 분리 (B-M9) / 캠페인 통합 검사 API (C-발견4) / 핫리로드 메모리 예산 (C-M7) / 06에 evasion 소유권 명시 (B-M14 후속) / batch 처리량 SLO (B-M11) / Clean Room SOP 명문화 (Minor 4)

## 6. 메타 관찰 (교차 리뷰 프로세스 자체에 대해)

- **수렴이 강했다**: 5개 축(라이선스 전파, 검수 체계, 출력 어휘, 도그휘슬 미스매치, 문맥 분류기)은 3개 AI가 서로 다른 표현으로 같은 곳을 찔렀다 — 신뢰도 높음.
- **교차 검증이 실제로 오류를 잡았다**: Codex의 B-M14(입력 누락에 의한 오판), agy의 C-C1(설계 오독)·"18건 전부 반영" 과신, 단일 리뷰였으면 그대로 반영될 뻔한 항목들이 걸러짐.
- **각자의 고유 기여**: Claude=라이선스-사업모델 충돌·검수자 인적 리스크, Codex=출력 어휘-법무 모순·release_policy·이전 리뷰 갭 적발, agy=구현 레벨 함정(OOM, 토크나이저, 사용자 사전, excerpt 제약).
