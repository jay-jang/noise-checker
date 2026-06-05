"""마이그레이션 + active 게이트 트리거 검증.

DATABASE_URL로 PostgreSQL에 접속할 수 없으면 전체를 skip한다 (@pytest.mark.db).
실행: DATABASE_URL=... uv run pytest tests/test_migrations.py
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.db

DEFAULT_DATABASE_URL = "postgresql+psycopg://noise:noise@localhost:5455/noise_checker"


def _test_database_url(url: str) -> str:
    """운영 DB 보호 가드 — 이 모듈의 왕복 테스트(downgrade base)는 DB를 전부 비우므로
    dbname이 _test로 끝나지 않으면 '<dbname>_test'를 (없으면 생성해) 대신 사용한다.
    test_loader/test_console_core는 자체 uuid 임시 DB 패턴이라 해당 없음."""
    base, _, dbname = url.rpartition("/")
    if dbname.endswith("_test"):
        return url
    try:
        import psycopg

        dsn = url.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(dsn, connect_timeout=3, autocommit=True) as conn:
            exists = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (f"{dbname}_test",)
            ).fetchone()
            if not exists:
                conn.execute(f'CREATE DATABASE "{dbname}_test"')
    except Exception:  # noqa: BLE001 — 접속 불가는 _connect()의 skip 경로가 처리
        pass
    return f"{base}/{dbname}_test"


DATABASE_URL = _test_database_url(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TABLES = {
    "source", "term", "term_evidence", "term_variant", "category", "term_category",
    "image_marker", "marker_reference_image", "marker_evidence", "incident",
    "composite_rule", "review_log", "dictionary_release", "candidate_queue",
}


def _connect():
    """psycopg 동기 연결. 실패하면 skip."""
    psycopg = pytest.importorskip("psycopg")
    dsn = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    try:
        return psycopg.connect(dsn, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001 — 접속 불가 전부 skip 사유
        pytest.skip(f"DATABASE_URL 접속 불가 — DB 테스트 skip: {exc}")


def _alembic(*args: str) -> None:
    env = {**os.environ, "DATABASE_URL": DATABASE_URL}
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT, env=env, check=True,
        capture_output=True, text=True,
    )


@pytest.fixture(scope="module")
def migrated_db():
    # 접속 가능 여부를 먼저 확인 (불가 시 skip)
    _connect().close()
    _alembic("upgrade", "head")
    yield
    # 모듈 종료 후 정리는 하지 않음 (다음 테스트/CI에서 재사용 가능 상태 유지)


def _insert_source(cur) -> int:
    cur.execute(
        "INSERT INTO source (title, source_type, license_class) "
        "VALUES ('테스트 출처', 'internal', 'permissive') RETURNING id"
    )
    return cur.fetchone()[0]


def _insert_term(cur, nkey: str, status: str = "draft") -> int:
    cur.execute(
        "INSERT INTO term (surface, normalized_key, term_kind, origin_story, meaning, "
        "severity, status) VALUES (%s, %s, 'word', '유래', '의미', 3, %s) RETURNING id",
        (nkey, nkey, status),
    )
    return cur.fetchone()[0]


def test_tables_exist(migrated_db):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            present = {r[0] for r in cur.fetchall()}
        assert present >= EXPECTED_TABLES, f"누락 테이블: {EXPECTED_TABLES - present}"
    finally:
        conn.close()


def test_category_seed(migrated_db):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM category")
            codes = {r[0] for r in cur.fetchall()}
        expected = {
            "misogyny", "misandry", "region_hate", "deceased", "disability",
            "race_nation", "politics", "sexual_minority", "age", "religion",
            "community_jargon",
        }
        assert codes == expected
    finally:
        conn.close()


def test_active_gate_blocks_without_evidence(migrated_db):
    """evidence 없는 term의 active 전환은 실패해야 한다."""
    import psycopg
    conn = _connect()
    try:
        with conn.cursor() as cur:
            tid = _insert_term(cur, "게이트없음")
        conn.commit()
        with conn.cursor() as cur, pytest.raises(psycopg.errors.RaiseException):
            cur.execute("UPDATE term SET status='active' WHERE id=%s", (tid,))
        conn.rollback()
    finally:
        conn.close()


def test_active_gate_blocks_direct_insert(migrated_db):
    """INSERT ... status='active' 우회도 막혀야 한다 (BEFORE INSERT)."""
    import psycopg
    conn = _connect()
    try:
        with conn.cursor() as cur, pytest.raises(psycopg.errors.RaiseException):
            cur.execute(
                "INSERT INTO term (surface, normalized_key, term_kind, origin_story, "
                "meaning, severity, status) "
                "VALUES ('직접', '직접삽입', 'word', '유래', '의미', 3, 'active')"
            )
        conn.rollback()
    finally:
        conn.close()


def test_active_gate_succeeds_with_origin_evidence(migrated_db):
    """origin evidence 추가 후 active 전환은 성공해야 한다."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            sid = _insert_source(cur)
            tid = _insert_term(cur, "게이트성공")
            cur.execute(
                "INSERT INTO term_evidence (term_id, source_id, evidence_type, added_by) "
                "VALUES (%s, %s, 'origin', 'pipeline:test')",
                (tid, sid),
            )
            cur.execute("UPDATE term SET status='active' WHERE id=%s", (tid,))
            cur.execute("SELECT status FROM term WHERE id=%s", (tid,))
            assert cur.fetchone()[0] == "active"
        conn.commit()
    finally:
        conn.close()


def test_last_origin_evidence_delete_blocked(migrated_db):
    """active 상태에서 마지막 origin evidence 삭제는 막혀야 한다."""
    import psycopg
    conn = _connect()
    try:
        with conn.cursor() as cur:
            sid = _insert_source(cur)
            tid = _insert_term(cur, "삭제차단")
            cur.execute(
                "INSERT INTO term_evidence (term_id, source_id, evidence_type, added_by) "
                "VALUES (%s, %s, 'definition', 'pipeline:test')",
                (tid, sid),
            )
            cur.execute("UPDATE term SET status='active' WHERE id=%s", (tid,))
        conn.commit()
        with conn.cursor() as cur, pytest.raises(psycopg.errors.RaiseException):
            cur.execute(
                "DELETE FROM term_evidence WHERE term_id=%s AND source_id=%s "
                "AND evidence_type='definition'",
                (tid, sid),
            )
        conn.rollback()
    finally:
        conn.close()


def test_watchlist_to_active_blocked(migrated_db):
    """watchlist→active 직접 전이는 막혀야 한다 (evidence가 있어도)."""
    import psycopg
    conn = _connect()
    try:
        with conn.cursor() as cur:
            sid = _insert_source(cur)
            tid = _insert_term(cur, "워치리스트전이", status="watchlist")
            cur.execute(
                "INSERT INTO term_evidence (term_id, source_id, evidence_type, added_by) "
                "VALUES (%s, %s, 'origin', 'pipeline:test')",
                (tid, sid),
            )
        conn.commit()
        with conn.cursor() as cur, pytest.raises(psycopg.errors.RaiseException):
            cur.execute("UPDATE term SET status='active' WHERE id=%s", (tid,))
        conn.rollback()
    finally:
        conn.close()


def test_excerpt_length_constraint(migrated_db):
    """excerpt 301자 INSERT는 CHECK 제약으로 실패해야 한다."""
    import psycopg
    conn = _connect()
    try:
        with conn.cursor() as cur:
            sid = _insert_source(cur)
            tid = _insert_term(cur, "발췌길이")
        conn.commit()
        with conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO term_evidence (term_id, source_id, evidence_type, excerpt, added_by) "
                "VALUES (%s, %s, 'usage', %s, 'pipeline:test')",
                (tid, sid, "가" * 301),
            )
        conn.rollback()
    finally:
        conn.close()


def test_roundtrip_downgrade_upgrade(migrated_db):
    """downgrade base → upgrade head 왕복 무결성."""
    _alembic("downgrade", "base")
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name = ANY(%s)",
                (list(EXPECTED_TABLES),),
            )
            assert cur.fetchone()[0] == 0, "downgrade 후에도 테이블이 남아있음"
    finally:
        conn.close()
    _alembic("upgrade", "head")
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            present = {r[0] for r in cur.fetchall()}
        assert present >= EXPECTED_TABLES
    finally:
        conn.close()


def _term_has_pattern_column(cur) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='term' AND column_name='pattern'"
    )
    return cur.fetchone() is not None


def test_term_pattern_column_added(migrated_db):
    """0002: term.pattern 컬럼(nullable)이 head 스키마에 존재한다."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            assert _term_has_pattern_column(cur), "term.pattern 컬럼 누락"
            cur.execute(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name='term' AND column_name='pattern'"
            )
            assert cur.fetchone()[0] == "YES"
    finally:
        conn.close()


def test_0002_roundtrip_drops_and_readds_pattern(migrated_db):
    """0002 down(→0001)에서 pattern 컬럼이 사라지고 up(→head)에서 복원된다."""
    _alembic("downgrade", "0001")
    conn = _connect()
    try:
        with conn.cursor() as cur:
            assert not _term_has_pattern_column(cur), "downgrade 후에도 pattern 잔존"
    finally:
        conn.close()
    _alembic("upgrade", "head")
    conn = _connect()
    try:
        with conn.cursor() as cur:
            assert _term_has_pattern_column(cur), "upgrade 후 pattern 미복원"
    finally:
        conn.close()
