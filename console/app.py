"""검수 콘솔 MVP (Streamlit) — M1.

로직은 전부 src/noise_checker/console_core.py에 있고, 이 파일은 얇은 UI 어댑터다.
페이지:
  ① 후보 큐    — pending 목록(kind/signal_score/urgency 정렬), payload 카드, 원문 기본 블러,
                  체크리스트 폼(04 §4 5항목), 승인/반려.
  ② 용어 브라우저 — status 필터, 상세(evidence·variants·incidents), 라이선스 게이트 프리뷰,
                  in_review→active 전환(프리뷰 통과 시에만 버튼 활성, DB 트리거가 최종 방어).
  ③ 감사 로그   — review_log 최근 200.
  ④ IAA         — 승인 표본 10% 결정적 무작위 추출 + second_review 기록.

실행: console/README.md 참조.
"""

from __future__ import annotations

import os

import streamlit as st
from sqlalchemy import create_engine, text

from noise_checker.console_core import (
    CHECKLIST_ITEMS,
    approve_candidate,
    license_gate_preview,
    record_second_review,
    reject_candidate,
)

DEFAULT_DATABASE_URL = "postgresql+psycopg://noise:noise@localhost:5455/noise_checker"

# 체크리스트 5항목 라벨 (04 §4)
CHECKLIST_LABELS = {
    "origin_source": "① origin 출처 ≥ 1 (청정 라이선스) 확인",
    "homonym_review": "② 동음이의어 검토 + safe_contexts 점검",
    "severity_basis": "③ severity 산정 근거 확인",
    "category": "④ 카테고리 적정성 확인",
    "legal_flag": "⑤ 법무 플래그(실명/노출) 검토",
}


@st.cache_resource
def get_engine():
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return create_engine(url, pool_pre_ping=True)


def reviewer_input() -> str:
    return st.sidebar.text_input(
        "검수자 (reviewer)",
        value=st.session_state.get("reviewer", ""),
        placeholder="human:이메일",
        key="reviewer",
    )


# ---------------------------------------------------------------------------
# ① 후보 큐
# ---------------------------------------------------------------------------
def page_queue(engine, reviewer: str) -> None:
    st.header("① 후보 큐 (pending)")
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, kind, collector, signal_score, urgency, payload, created_at "
            "FROM candidate_queue WHERE status='pending' "
            "ORDER BY CASE urgency WHEN 'urgent' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, "
            "signal_score DESC, created_at ASC"
        )).fetchall()

    if not rows:
        st.info("대기 중인 후보가 없습니다.")
        return

    for r in rows:
        cid, kind, collector, score, urgency, payload, created = r
        badge = "🔴 urgent" if urgency == "urgent" else urgency
        with st.expander(f"#{cid} · {kind} · {badge} · score={score:.2f} · {collector}"):
            _candidate_card(engine, cid, kind, payload, reviewer)


def _candidate_card(engine, cid: int, kind: str, payload: dict, reviewer: str) -> None:
    surface = payload.get("surface") or payload.get("name") or payload.get("title") or payload.get(
        "variant"
    ) or payload.get("target_surface") or "(미상)"
    st.write(f"**표제/대상**: {surface}")
    if payload.get("meaning"):
        st.write(f"**의미**: {payload['meaning']}")
    severity = payload.get("severity")
    legal_flag = bool(payload.get("legal_review_flag", False))
    if severity is not None:
        flag_label = "예" if legal_flag else "아니오"
        st.write(f"**severity**: {severity}  ·  **법무 플래그**: {flag_label}")

    # 혐오 원문 기본 블러 — expander 안에 넣어 펼쳐야 보이게.
    with st.expander("원문 보기 (블러 해제)"):
        st.json(payload)

    full_required = (severity is not None and int(severity) >= 5) or legal_flag
    st.caption(
        "severity≥5 또는 법무 플래그 → 풀 체크리스트 필수"
        if full_required
        else "경량 체크리스트 (저위험)"
    )

    checklist: dict[str, bool] = {}
    for item in CHECKLIST_ITEMS:
        checklist[item] = st.checkbox(CHECKLIST_LABELS[item], key=f"chk_{cid}_{item}")

    col_a, col_r = st.columns(2)
    with col_a:
        if st.button("승인", key=f"approve_{cid}", type="primary"):
            if not reviewer.strip():
                st.error("검수자를 입력하세요.")
            else:
                _do_approve(engine, cid, reviewer, checklist)
    with col_r:
        reason = st.text_input("반려 사유", key=f"reason_{cid}")
        if st.button("반려", key=f"reject_{cid}"):
            if not reviewer.strip():
                st.error("검수자를 입력하세요.")
            elif not reason.strip():
                st.error("반려 사유를 입력하세요.")
            else:
                with engine.begin() as conn:
                    reject_candidate(conn, cid, reviewer, reason)
                st.success(f"후보 #{cid} 반려됨")
                st.rerun()


def _do_approve(engine, cid: int, reviewer: str, checklist: dict) -> None:
    try:
        with engine.begin() as conn:
            result = approve_candidate(conn, cid, reviewer, checklist)
    except ValueError as e:
        st.error(f"승인 거부: {e}")
        return
    st.success(
        f"후보 #{cid} 승인 — term_id={result.term_id}, marker_id={result.marker_id}, "
        f"variants={result.variant_ids}"
    )
    st.rerun()


# ---------------------------------------------------------------------------
# ② 용어 브라우저
# ---------------------------------------------------------------------------
def page_terms(engine, reviewer: str) -> None:
    st.header("② 용어 브라우저")
    statuses = ["draft", "watchlist", "in_review", "active", "deprecated", "rejected"]
    selected = st.multiselect("status 필터", statuses, default=["in_review", "active"])
    if not selected:
        st.info("status를 하나 이상 선택하세요.")
        return

    with engine.connect() as conn:
        terms = conn.execute(
            text(
                "SELECT id, surface, term_kind, severity, status, provenance_class, ambiguity "
                "FROM term WHERE status = ANY(:ss) ORDER BY updated_at DESC LIMIT 200"
            ),
            {"ss": selected},
        ).fetchall()

    if not terms:
        st.info("해당 status의 용어가 없습니다.")
        return

    for t in terms:
        tid, surface, kind, severity, status, prov, ambiguity = t
        with st.expander(f"#{tid} · {surface} · {status} · sev={severity} · {prov}"):
            _term_detail(engine, tid, status, reviewer)


def _term_detail(engine, tid: int, status: str, reviewer: str) -> None:
    with engine.connect() as conn:
        evidence = conn.execute(
            text(
                "SELECT s.title, s.source_type, s.license, s.license_class, te.evidence_type "
                "FROM term_evidence te JOIN source s ON s.id = te.source_id "
                "WHERE te.term_id = :t"
            ),
            {"t": tid},
        ).fetchall()
        variants = conn.execute(
            text("SELECT variant, variant_kind, verified FROM term_variant WHERE term_id=:t"),
            {"t": tid},
        ).fetchall()
        incidents = conn.execute(
            text(
                "SELECT title, occurred_at, disclosable FROM incident WHERE term_id=:t"
            ),
            {"t": tid},
        ).fetchall()

    st.subheader("evidence")
    if evidence:
        st.table([
            {"출처": e[0], "type": e[1], "license": e[2], "class": e[3], "용도": e[4]}
            for e in evidence
        ])
    else:
        st.caption("evidence 없음")

    st.subheader("variants")
    st.table([{"변형": v[0], "kind": v[1], "verified": v[2]} for v in variants] or [{}])

    st.subheader("incidents (내부 — 제목 비노출 원칙)")
    st.caption(f"{len(incidents)}건 (disclosable=true만 외부 노출)")

    # 라이선스 게이트 프리뷰
    st.subheader("라이선스 게이트 프리뷰 (게이트 0)")
    classes = [e[3] for e in evidence]
    gate = license_gate_preview(classes)
    if gate.passes:
        st.success(f"통과 · effective_license={gate.effective_license} · {gate.provenance_class}")
    else:
        st.error(f"차단 · {gate.reason}")

    # in_review → active 전환 (프리뷰 통과 시에만 버튼 활성; DB 트리거가 최종 방어)
    if status == "in_review":
        disabled = not gate.passes or not reviewer.strip()
        if st.button("active 전환", key=f"activate_{tid}", disabled=disabled):
            _activate_term(engine, tid, reviewer)
        if not gate.passes:
            st.caption("게이트 프리뷰 미통과 — 전환 불가")


def _activate_term(engine, tid: int, reviewer: str) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE term SET status='active' WHERE id=:t"), {"t": tid})
            conn.execute(
                text(
                    "INSERT INTO review_log (entity_type, entity_id, action, reviewer, rationale) "
                    "VALUES ('term', :t, 'activated', :r, 'in_review→active (게이트 프리뷰 통과)')"
                ),
                {"t": tid, "r": reviewer},
            )
    except Exception as e:  # noqa: BLE001 — DB 트리거 예외를 사용자에게 표시
        st.error(f"active 전환 거부 (DB 트리거): {e}")
        return
    st.success(f"term #{tid} active 전환됨")
    st.rerun()


# ---------------------------------------------------------------------------
# ③ 감사 로그
# ---------------------------------------------------------------------------
def page_audit(engine) -> None:
    st.header("③ 감사 로그 (review_log 최근 200)")
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT reviewed_at, entity_type, entity_id, action, reviewer, rationale "
            "FROM review_log ORDER BY reviewed_at DESC LIMIT 200"
        )).fetchall()
    if not rows:
        st.info("로그가 없습니다.")
        return
    st.dataframe([
        {
            "시각": str(r[0]), "entity": f"{r[1]}#{r[2]}", "action": r[3],
            "reviewer": r[4], "rationale": r[5],
        }
        for r in rows
    ])


# ---------------------------------------------------------------------------
# ④ IAA — 결정적 10% 표본 + second_review
# ---------------------------------------------------------------------------
def page_iaa(engine, reviewer: str) -> None:
    st.header("④ IAA — 승인 표본 이중검수")
    st.caption("승인된 term을 결정적 의사난수(md5)로 10% 추출 → second_review 기록")
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, surface, severity, status FROM term "
            "WHERE id IN (SELECT entity_id FROM review_log "
            "            WHERE entity_type='term' AND action='approved') "
            "AND ('x' || substr(md5(id::text), 1, 8))::bit(32)::bigint % 10 = 0 "
            "ORDER BY id DESC LIMIT 100"
        )).fetchall()
    if not rows:
        st.info("이중검수 표본이 없습니다 (승인 term 부족).")
        return
    for r in rows:
        tid, surface, severity, status = r
        with st.expander(f"#{tid} · {surface} · sev={severity} · {status}"):
            agree = st.radio("판정 일치 여부", ["일치", "불일치"], key=f"iaa_agree_{tid}")
            note = st.text_input("메모", key=f"iaa_note_{tid}")
            if st.button("second_review 기록", key=f"iaa_btn_{tid}"):
                if not reviewer.strip():
                    st.error("검수자를 입력하세요.")
                else:
                    with engine.begin() as conn:
                        record_second_review(
                            conn, "term", tid, reviewer, agree == "일치", note
                        )
                    st.success(f"term #{tid} second_review 기록됨")
                    st.rerun()


# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="noise-checker 검수 콘솔", layout="wide")
    st.title("noise-checker 검수 콘솔 (M1)")
    engine = get_engine()
    reviewer = reviewer_input()
    if not reviewer.strip():
        st.sidebar.warning("승인/반려/전환 전에 검수자를 입력하세요.")

    page = st.sidebar.radio(
        "페이지", ["① 후보 큐", "② 용어 브라우저", "③ 감사 로그", "④ IAA"]
    )
    if page == "① 후보 큐":
        page_queue(engine, reviewer)
    elif page == "② 용어 브라우저":
        page_terms(engine, reviewer)
    elif page == "③ 감사 로그":
        page_audit(engine)
    else:
        page_iaa(engine, reviewer)


if __name__ == "__main__":
    main()
