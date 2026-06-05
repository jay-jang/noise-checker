# 검수 콘솔 (M1 MVP)

후보 큐 승인/반려, 라이선스 게이트 프리뷰, IAA 이중검수 기록 (docs/04 §3·§4, docs/05 M1).
로직은 `src/noise_checker/console_core.py`(순수, 테스트 대상), UI는 `console/app.py`(얇음).

## 실행

```
uv sync --extra console
export DATABASE_URL='postgresql+psycopg://noise:noise@localhost:5455/noise_checker'
uv run streamlit run console/app.py
```

## 페이지

- ① 후보 큐: pending 후보를 kind/urgency/signal_score 순 정렬, 혐오 원문 기본 블러(펼침 토글),
  체크리스트(04 §4 5항목) 후 승인/반려. severity≥5·법무 플래그는 풀 체크리스트 강제.
  승인은 source(URL dedupe)/term(in_review)/evidence/category/variant/incident를 단일 트랜잭션 적재.
- ② 용어 브라우저: status 필터, evidence·variants·incidents 상세, 라이선스 게이트 프리뷰.
  `in_review→active` 전환은 프리뷰 통과 시에만 버튼 활성 — **DB 트리거가 최종 방어선**.
- ③ 감사 로그: review_log 최근 200건.
- ④ IAA: 승인 term을 결정적 의사난수(md5)로 10% 추출 → second_review 기록.
