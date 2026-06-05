"""검수 콘솔 순수 로직 + 트랜잭션 테스트 (M1).

순수 로직(게이트 프리뷰/license_class 매핑/체크리스트 강제)은 DB 없이 검증한다.
트랜잭션 테스트(@pytest.mark.db)는 **임시 DB 패턴**으로 격리한다:
  DATABASE_URL 서버에 uuid 접미사 임시 데이터베이스를 CREATE → alembic upgrade head →
  테스트 → DROP. 공유 중인 noise_checker DB·docker compose는 절대 건드리지 않는다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from noise_checker.console_core import (
    CHECKLIST_ITEMS,
    approve_candidate,
    license_class_from_string,
    license_gate_preview,
    payload_to_rows,
    record_second_review,
    reject_candidate,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql+psycopg://noise:noise@localhost:5455/noise_checker"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
UNJI_PAYLOAD_PATH = PROJECT_ROOT / "data" / "seed" / "example-payload-new-term-unji.json"


# ===========================================================================
# 순수 로직 — DB 불필요
# ===========================================================================
class TestLicenseGatePreview:
    def test_all_permissive_passes_permissive_core(self):
        g = license_gate_preview(["permissive", "permissive"])
        assert g.passes is True
        assert g.effective_license == "자체"
        assert g.provenance_class == "permissive_core"

    def test_share_alike_passes_share_alike_core(self):
        g = license_gate_preview(["permissive", "share_alike"])
        assert g.passes is True
        assert g.effective_license == "CC BY-SA 4.0"
        assert g.provenance_class == "share_alike_core"

    def test_unknown_blocks_restricted_eval_only(self):
        g = license_gate_preview(["permissive", "unknown"])
        assert g.passes is False
        assert g.blocking == ["unknown"]
        assert g.provenance_class == "restricted_eval_only"

    def test_noncommercial_and_restricted_block(self):
        g = license_gate_preview(["noncommercial", "restricted", "share_alike"])
        assert g.passes is False
        assert g.blocking == ["noncommercial", "restricted"]
        # SA가 끼어 있어도 차단이면 restricted_eval_only, effective는 SA 전파 표기
        assert g.provenance_class == "restricted_eval_only"
        assert g.effective_license == "CC BY-SA 4.0"

    def test_empty_does_not_pass(self):
        g = license_gate_preview([])
        assert g.passes is False
        assert g.provenance_class == "restricted_eval_only"


class TestLicenseClassMapping:
    def test_cc_by_sa_variants(self):
        assert license_class_from_string("CC BY-SA 4.0", "wiki")[0] == "share_alike"
        assert license_class_from_string("CC-BY-SA 2.0 KR", "wiki")[0] == "share_alike"

    def test_nc_blocks(self):
        assert license_class_from_string("CC BY-NC-SA 2.0 KR", "dataset")[0] == "noncommercial"
        assert license_class_from_string("CC BY-NC 4.0", "dataset")[0] == "noncommercial"

    def test_nd_blocks(self):
        assert license_class_from_string("CC BY-ND 4.0", "dataset")[0] == "no_derivatives"

    def test_permissive_licenses(self):
        assert license_class_from_string("MIT", "dataset")[0] == "permissive"
        assert license_class_from_string("Apache-2.0", "dataset")[0] == "permissive"
        assert license_class_from_string("CC BY 4.0", "wiki")[0] == "permissive"
        assert license_class_from_string("CC0", "dataset")[0] == "permissive"

    def test_unknown_default_blocks(self):
        # 불명 라이선스는 unknown (NC와 동일하게 차단 기본값, 02 §5)
        assert license_class_from_string("자체 약관 협의 필요", "dataset")[0] == "unknown"
        assert license_class_from_string(None, "dataset")[0] == "unknown"

    def test_news_is_permissive_with_note(self):
        # 핵심 해석: 뉴스는 사실 추출만 → 게이트 차단 대상 아님 → permissive + note.
        lic_class, note = license_class_from_string("언론사 저작권", "news")
        assert lic_class == "permissive"
        assert note is not None and "본문 복제 금지" in note

    def test_internal_is_permissive(self):
        assert license_class_from_string(None, "internal")[0] == "permissive"


class TestPayloadToRows:
    def _unji(self) -> dict:
        return json.loads(UNJI_PAYLOAD_PATH.read_text())

    def test_unji_in_review_and_provenance(self):
        doc = self._unji()
        planned = payload_to_rows(doc["payload"], doc["kind"], "human:test@x.com")
        assert planned.term["status"] == "in_review"
        assert planned.term["normalized_key"]  # normalizer 사용
        # 운지 evidence는 CC BY-SA 4.0 단일 → share_alike_core
        assert planned.term["provenance_class"] == "share_alike_core"
        assert planned.gate.passes is True
        # categories 3종, source 1건
        assert set(planned.categories) == {"deceased", "community_jargon", "politics"}
        assert len(planned.sources) == 1
        assert planned.sources[0].license_class == "share_alike"
        # 변형 미관찰 → 빈 리스트
        assert planned.variants == []

    def test_needs_verification_forces_draft(self):
        doc = self._unji()
        doc["payload"]["needs_verification"] = True
        planned = payload_to_rows(doc["payload"], doc["kind"], "human:test@x.com")
        assert planned.term["status"] == "draft"

    def test_variants_observed_planned_unverified(self):
        doc = self._unji()
        doc["payload"]["variants_observed"] = [
            {"variant": "ㅇㅈ", "variant_kind": "chosung"},
        ]
        planned = payload_to_rows(doc["payload"], doc["kind"], "human:test@x.com")
        assert len(planned.variants) == 1
        assert planned.variants[0]["verified"] is False
        assert planned.variants[0]["normalized_key"]

    def test_word_term_has_no_pattern(self):
        # 비-pattern(word) 항목은 pattern이 None (다른 kind 영향 없음).
        doc = self._unji()
        planned = payload_to_rows(doc["payload"], doc["kind"], "human:test@x.com")
        assert planned.term["pattern"] is None

    def test_pattern_term_carries_regex(self):
        # term_kind='pattern' 후보의 payload.pattern이 term 행 계획에 보존된다(버그2 ③).
        doc = json.loads(
            (PROJECT_ROOT / "data" / "seed" / "candidates" / "new_term--no-ending-pattern.json")
            .read_text()
        )
        planned = payload_to_rows(doc["payload"], doc["kind"], "human:test@x.com")
        assert planned.term["term_kind"] == "pattern"
        assert planned.term["pattern"] == r"(.+)노[\.!\?…]*$"


# ===========================================================================
# 트랜잭션 — 임시 DB 격리 (@pytest.mark.db)
# ===========================================================================
db = pytest.mark.db


def _alembic_upgrade(db_url: str) -> None:
    env = {**os.environ, "DATABASE_URL": db_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT, env=env, check=True, capture_output=True, text=True,
    )


@pytest.fixture(scope="module")
def temp_engine():
    """임시 데이터베이스를 만들고 alembic upgrade 후 sqlalchemy Engine을 준다.

    공유 noise_checker/compose를 건드리지 않도록 서버의 maintenance DB(postgres)에
    접속해 uuid 접미사 임시 DB를 CREATE/DROP한다.
    """
    psycopg = pytest.importorskip("psycopg")
    sqlalchemy = pytest.importorskip("sqlalchemy")

    # DATABASE_URL에서 서버 좌표를 분리하고 maintenance DB(postgres)로 admin 연결.
    base = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    head, _, _olddb = base.rpartition("/")
    admin_dsn = f"{head}/postgres"
    temp_name = f"nc_console_test_{uuid.uuid4().hex[:12]}"

    try:
        admin = psycopg.connect(admin_dsn, connect_timeout=3, autocommit=True)
    except Exception as exc:  # noqa: BLE001 — 접속 불가 전부 skip
        pytest.skip(f"DATABASE_URL 접속 불가 — DB 테스트 skip: {exc}")

    try:
        with admin.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{temp_name}"')
    except Exception as exc:  # noqa: BLE001
        admin.close()
        pytest.skip(f"임시 DB 생성 불가 — skip: {exc}")

    temp_url = f"{head}/{temp_name}".replace("postgresql://", "postgresql+psycopg://")
    try:
        _alembic_upgrade(temp_url)
    except subprocess.CalledProcessError as exc:
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{temp_name}"')
        admin.close()
        pytest.fail(f"alembic upgrade 실패: {exc.stderr}")

    engine = sqlalchemy.create_engine(temp_url, poolclass=sqlalchemy.pool.NullPool)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (temp_name,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{temp_name}"')
        admin.close()


@pytest.fixture
def clean_db(temp_engine):
    """각 DB 테스트 전에 적재 테이블을 비워 테스트 간 격리 (normalized_key 충돌 방지).

    임시 DB는 module 스코프로 공유하되, 행은 함수마다 초기화한다.
    """
    from sqlalchemy import text

    with temp_engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE candidate_queue, review_log, incident, composite_rule, "
            "term_category, term_variant, term_evidence, marker_evidence, "
            "image_marker, term, source RESTART IDENTITY CASCADE"
        ))
    return temp_engine


def _insert_candidate(conn, doc: dict) -> int:
    from sqlalchemy import text

    dedup = uuid.uuid4().hex  # 테스트 격리: dedup_key 충돌 회피
    cid = conn.execute(
        text(
            "INSERT INTO candidate_queue (payload, kind, collector, signal_score, "
            "urgency, dedup_key) "
            "VALUES (CAST(:p AS JSONB), :k, :c, :s, 'normal', :d) RETURNING id"
        ),
        {
            "p": json.dumps(doc["payload"]),
            "k": doc["kind"],
            "c": doc.get("collector", "agent:test"),
            "s": 1.0,
            "d": dedup,
        },
    ).fetchone()[0]
    return cid


def _full_checklist() -> dict:
    return {item: True for item in CHECKLIST_ITEMS}


@db
def test_approve_unji_full_transaction(clean_db):
    """운지(severity 5) 후보 승인 — term/source/evidence/category 적재 + review_log."""
    from sqlalchemy import text

    doc = json.loads(UNJI_PAYLOAD_PATH.read_text())
    with clean_db.begin() as conn:
        cid = _insert_candidate(conn, doc)
        result = approve_candidate(conn, cid, "human:reviewer@x.com", _full_checklist())

    assert result.term_id is not None
    assert len(result.source_ids) == 1
    with clean_db.connect() as conn:
        # term은 in_review (active 직접 적재 금지)
        status = conn.execute(
            text("SELECT status, provenance_class FROM term WHERE id=:t"),
            {"t": result.term_id},
        ).fetchone()
        assert status[0] == "in_review"
        assert status[1] == "share_alike_core"
        # evidence 1건
        ev = conn.execute(
            text("SELECT count(*) FROM term_evidence WHERE term_id=:t"), {"t": result.term_id}
        ).scalar()
        assert ev == 1
        # category 3종 매핑
        cats = conn.execute(
            text("SELECT count(*) FROM term_category WHERE term_id=:t"), {"t": result.term_id}
        ).scalar()
        assert cats == 3
        # candidate 승인 처리
        cstatus = conn.execute(
            text("SELECT status FROM candidate_queue WHERE id=:c"), {"c": cid}
        ).scalar()
        assert cstatus == "approved"
        # review_log approved 기록
        logged = conn.execute(
            text(
                "SELECT action, reviewer FROM review_log "
                "WHERE entity_type='term' AND entity_id=:t"
            ),
            {"t": result.term_id},
        ).fetchall()
        actions = {r[0] for r in logged}
        assert "approved" in actions
        assert all(r[1] == "human:reviewer@x.com" for r in logged)


@db
def test_approve_pattern_term_persists_pattern(clean_db):
    """pattern 후보 승인 시 term.pattern 컬럼에 정규식이 적재된다(버그2 ③ 왕복)."""
    from sqlalchemy import text

    doc = json.loads(
        (PROJECT_ROOT / "data" / "seed" / "candidates" / "new_term--no-ending-pattern.json")
        .read_text()
    )
    with clean_db.begin() as conn:
        cid = _insert_candidate(conn, doc)
        result = approve_candidate(conn, cid, "human:reviewer@x.com", _full_checklist())

    assert result.term_id is not None
    with clean_db.connect() as conn:
        row = conn.execute(
            text("SELECT term_kind, pattern FROM term WHERE id=:t"),
            {"t": result.term_id},
        ).fetchone()
        assert row[0] == "pattern"
        assert row[1] == r"(.+)노[\.!\?…]*$"


@db
def test_url_dedupe_shares_source(clean_db):
    """같은 evidence URL을 가진 두 후보가 source 한 행을 공유해야 한다."""
    from sqlalchemy import text

    base = json.loads(UNJI_PAYLOAD_PATH.read_text())
    shared_url = base["payload"]["evidence"][0]["url"]

    # 두 번째 후보: surface만 바꿔 같은 URL 재사용
    second = json.loads(UNJI_PAYLOAD_PATH.read_text())
    second["payload"]["surface"] = "운지천"

    with clean_db.begin() as conn:
        c1 = _insert_candidate(conn, base)
        r1 = approve_candidate(conn, c1, "human:r@x.com", _full_checklist())
        c2 = _insert_candidate(conn, second)
        r2 = approve_candidate(conn, c2, "human:r@x.com", _full_checklist())

    assert r1.source_ids == r2.source_ids  # 같은 source 재사용
    with clean_db.connect() as conn:
        n = conn.execute(
            text("SELECT count(*) FROM source WHERE url=:u"), {"u": shared_url}
        ).scalar()
        assert n == 1


@db
def test_needs_verification_lands_draft(clean_db):
    from sqlalchemy import text

    doc = json.loads(UNJI_PAYLOAD_PATH.read_text())
    doc["payload"]["needs_verification"] = True
    with clean_db.begin() as conn:
        cid = _insert_candidate(conn, doc)
        result = approve_candidate(conn, cid, "human:r@x.com", _full_checklist())
    with clean_db.connect() as conn:
        status = conn.execute(
            text("SELECT status FROM term WHERE id=:t"), {"t": result.term_id}
        ).scalar()
        assert status == "draft"


@db
def test_severity5_incomplete_checklist_raises(clean_db):
    """severity 5 항목인데 체크리스트 미충족이면 예외 + 트랜잭션 롤백."""
    from sqlalchemy import text

    doc = json.loads(UNJI_PAYLOAD_PATH.read_text())  # severity=5
    partial = {item: True for item in CHECKLIST_ITEMS}
    partial["legal_flag"] = False  # 한 항목 누락

    with clean_db.connect() as conn:
        trans = conn.begin()
        cid = _insert_candidate(conn, doc)
        with pytest.raises(ValueError, match="풀 체크리스트"):
            approve_candidate(conn, cid, "human:r@x.com", partial)
        trans.rollback()

    # 롤백되었으므로 term이 적재되지 않아야 한다.
    with clean_db.connect() as conn:
        n = conn.execute(text("SELECT count(*) FROM term")).scalar()
        assert n == 0


@db
def test_reject_candidate(clean_db):
    from sqlalchemy import text

    doc = json.loads(UNJI_PAYLOAD_PATH.read_text())
    with clean_db.begin() as conn:
        cid = _insert_candidate(conn, doc)
        reject_candidate(conn, cid, "human:r@x.com", "근거 출처 신뢰도 부족")
    with clean_db.connect() as conn:
        cstatus = conn.execute(
            text("SELECT status FROM candidate_queue WHERE id=:c"), {"c": cid}
        ).scalar()
        assert cstatus == "rejected"
        log = conn.execute(
            text("SELECT action, rationale FROM review_log WHERE action='rejected'")
        ).fetchone()
        assert log is not None
        assert "신뢰도" in log[1]
        # term은 적재되지 않음
        assert conn.execute(text("SELECT count(*) FROM term")).scalar() == 0


_INCIDENT_DOC = {
    "kind": "incident",
    "collector": "agent:test",
    "payload": {
        "title": "테스트사 포스터 집게손 논란",
        "occurred_at": "2021-05-01",
        "medium": "ad",
        "related_surface": "집게손가락",
        "sample_text": "포스터 일러스트",
        "source_url": "https://news.example.com/a1",
    },
}


@db
def test_approve_incident_resolves_marker(clean_db):
    """related_surface가 term이 아니라 marker(집게손가락)인 incident 승인."""
    from sqlalchemy import text

    with clean_db.begin() as conn:
        mid = conn.execute(text(
            "INSERT INTO image_marker (name, marker_kind, origin_story, severity, "
            "status, detection_method) "
            "VALUES ('집게손가락 (엄지·검지 오므린 손 모양)', 'hand_sign', '유래', 3, "
            "'draft', '{manual}') RETURNING id"  # '이름 (부연)' 규약 — 앞부분 일치 해석
        )).fetchone()[0]
        cid = _insert_candidate(conn, _INCIDENT_DOC)
        result = approve_candidate(conn, cid, "human:r@x.com", _full_checklist())

    assert result.incident_ids
    with clean_db.connect() as conn:
        row = conn.execute(
            text("SELECT term_id, marker_id, disclosable FROM incident WHERE id=:i"),
            {"i": result.incident_ids[0]},
        ).fetchone()
        assert row[0] is None and row[1] == mid
        assert row[2] is False  # 노출 거버넌스 기본값


@db
def test_approve_incident_unresolvable_surface_raises(clean_db):
    """related_surface가 term/marker 어느 쪽도 아니면 명확한 오류 (DB 제약 위반 전에)."""
    with clean_db.begin() as conn:
        cid = _insert_candidate(conn, _INCIDENT_DOC)
        with pytest.raises(ValueError, match="먼저 승인"):
            approve_candidate(conn, cid, "human:r@x.com", _full_checklist())


@db
def test_record_second_review(clean_db):
    from sqlalchemy import text

    doc = json.loads(UNJI_PAYLOAD_PATH.read_text())
    with clean_db.begin() as conn:
        cid = _insert_candidate(conn, doc)
        result = approve_candidate(conn, cid, "human:r1@x.com", _full_checklist())
        record_second_review(
            conn, "term", result.term_id, "human:r2@x.com", agree=True, note="severity 동의"
        )
    with clean_db.connect() as conn:
        row = conn.execute(
            text(
                "SELECT reviewer, new_value FROM review_log "
                "WHERE action='second_review' AND entity_id=:t"
            ),
            {"t": result.term_id},
        ).fetchone()
        assert row is not None
        assert row[0] == "human:r2@x.com"
        assert row[1]["agree"] is True
