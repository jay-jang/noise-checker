"""M1 잔여 4개 용어 승격 — 청정 origin/definition evidence 추가 후 draft/in_review→active.

근거: reports/m1-cleanup-research-2026-06-08.md (lexicon-researcher 리서치, WebFetch 검증).
뉴스/학술/정부 = 사실 추출 → permissive+notes. 모든 evidence URL은 에이전트가 직접 열람 확인.
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text

REVIEWER = "human:nuinuri@gmail.com"

# surface -> [evidence...]. evidence_type 중 origin/definition가 active 게이트 통과 근거.
EVIDENCE = {
    "정신병자": [
        {
            "url": "https://www.korean.go.kr/front/imprv/refineView.do?mn_id=158&imprv_refine_seq=18721",
            "title": "국립국어원 다듬은 말 — '정신병자'→'정신 질환자'",
            "source_type": "government",
            "license_class": "permissive",
            "evidence_type": "definition",
            "excerpt": "국립국어원 '다듬은 말': '정신병자'를 사람보다 질환에 초점을 둔 낙인성 표현으로 분류, 순화어 '정신 질환자' 제시.",
            "notes": "정부 언어순화 1차 출처(사실 추출). 용어 자체를 낙인 표현으로 직접 분류.",
        },
        {
            "url": "https://www.ablenews.co.kr/news/articleView.html?idxno=221296",
            "title": "에이블뉴스 — 정치인 '정신병자' 발언 장애차별 진정",
            "source_type": "news",
            "license_class": "permissive",
            "evidence_type": "incident",
            "excerpt": "홍준표·이철우의 '정신병자' 표현을 장애 차별로 진정 — 표면형 정확 일치 사용 실태.",
            "notes": "뉴스: 사실 추출만, 본문 복제 금지.",
        },
    ],
    "개저씨": [
        {
            "url": "https://www.korean.go.kr/nkview/nklife/2017_3/27_0301.pdf",
            "title": "이정복, '한국어와 한국 사회의 혐오, 차별 표현', 새국어생활 27(3), 2017",
            "source_type": "academic",
            "license_class": "permissive",
            "evidence_type": "definition",
            "excerpt": "'개저씨'는 '개+아저씨'의 구성이며, 주로 예의 없고 공중도덕을 잘 지키지 않는 무례한 남성에게 쓴다. '냄저·개저씨·한남충'을 남혐 표현으로 분류.",
            "notes": "학술 인용(사실 참조): 정의·합성 구성. 전문 발췌 금지. 기존 출처 없는 통계 단정을 대체하는 근거.",
        },
    ],
    "애자": [
        {
            "url": "https://news.sbs.co.kr/news/endPage.do?news_id=N1002934649",
            "title": "SBS 취재파일 — 장애인 비하 용어 '애자'",
            "source_type": "news",
            "license_class": "permissive",
            "evidence_type": "origin",
            "excerpt": "'애자'는 '장애자'를 줄인 일종의 은어로, 놀림·공격 대상에게 욕으로 사용됐다.",
            "notes": "뉴스: 사실 추출만. '장애자 파생' 어원을 청정 출처가 직접 명시.",
        },
    ],
    "상폐녀": [
        {
            "url": "https://news.sbs.co.kr/news/endPage.do?news_id=N1002819998",
            "title": "SBS 전망대 — 온라인 여성혐오 표현 '상폐녀'",
            "source_type": "news",
            "license_class": "permissive",
            "evidence_type": "definition",
            "excerpt": "상장폐지녀(상폐녀)는 미혼·노처녀 여성을 '팔리지도 않는 물건'으로 비하하는 표현. 김치녀·성괴와 함께 온라인 여성혐오로 분류.",
            "notes": "뉴스: 사실 추출만. 발원 커뮤니티는 헤지 유지.",
        },
    ],
}


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL 미설정", file=sys.stderr)
        return 1
    eng = create_engine(url)
    for surface, evs in EVIDENCE.items():
        with eng.begin() as conn:
            tid = conn.execute(
                text("SELECT id, status FROM term WHERE surface=:s ORDER BY id LIMIT 1"),
                {"s": surface},
            ).fetchone()
            if tid is None:
                print(f"{surface}: term 없음 — 스킵")
                continue
            term_id, status = tid[0], tid[1]
            for ev in evs:
                sid = conn.execute(
                    text(
                        "INSERT INTO source (url, title, source_type, license_class, "
                        "reliability, notes) VALUES (:u,:t,:st,:lc,4,:n) "
                        "ON CONFLICT (url) DO UPDATE SET title=EXCLUDED.title RETURNING id"
                    ),
                    {"u": ev["url"], "t": ev["title"], "st": ev["source_type"],
                     "lc": ev["license_class"], "n": ev["notes"]},
                ).fetchone()[0]
                conn.execute(
                    text(
                        "INSERT INTO term_evidence (term_id, source_id, evidence_type, "
                        "added_by, excerpt) VALUES (:t,:s,:et,:by,:ex) "
                        "ON CONFLICT (term_id, source_id, evidence_type) DO NOTHING"
                    ),
                    {"t": term_id, "s": sid, "et": ev["evidence_type"],
                     "by": REVIEWER, "ex": ev["excerpt"][:300]},
                )
            # draft/in_review → active (트리거가 origin/definition+라이선스 게이트 검증)
            try:
                conn.execute(
                    text("UPDATE term SET status='active' WHERE id=:t"), {"t": term_id}
                )
                conn.execute(
                    text(
                        "INSERT INTO review_log (entity_type, entity_id, action, reviewer, rationale) "
                        "VALUES ('term', :t, 'activated', :r, :msg)"
                    ),
                    {"t": term_id, "r": REVIEWER,
                     "msg": f"{status}→active (M1 정리: 청정 출처 재근거화, reports/m1-cleanup-research-2026-06-08)"},
                )
                print(f"{surface}: {status}→active (evidence +{len(evs)})")
            except Exception as e:  # noqa: BLE001 — 트리거 거부 표면화
                print(f"{surface}: active 거부 — {str(e)[:120]}")
                raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
