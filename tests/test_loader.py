"""후보 적재 도구(loader) 테스트.

dry-run 경로는 DB 없이 검증/래핑/점수화를 확인한다.
@pytest.mark.db 경로는 DATABASE_URL 서버에 임시 데이터베이스(uuid 접미사)를
생성·migrate·적재·dedup·DROP 한다 — 공유 중인 noise_checker DB는 건드리지 않는다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from noise_checker.loader import (
    LEGACY_COLLECTOR,
    build_validator,
    compute_dedup_key,
    compute_signal_score,
    discover_paths,
    insert_items,
    is_legacy_term,
    prepare,
    run,
    wrap_legacy,
)
from noise_checker.normalizer import normalized_key

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = PROJECT_ROOT / "data" / "seed"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

NEW_TERM_PAYLOAD = SEED_DIR / "example-payload-new-term-unji.json"
INCIDENT_PAYLOAD = SEED_DIR / "example-payload-incident-tankday.json"
INVALID_FIXTURE = FIXTURE_DIR / "invalid-new-term-missing-negative.json"
LEGACY_FIXTURE = FIXTURE_DIR / "legacy-term-megal.json"


# ── dry-run / DB 불필요 경로 ────────────────────────────────────────────────


def test_prepare_accepts_valid_payload():
    validator = build_validator()
    result = prepare([NEW_TERM_PAYLOAD, INCIDENT_PAYLOAD], validator)
    assert result.failures == []
    assert len(result.items) == 2
    kinds = {item.kind for item in result.items}
    assert kinds == {"new_term", "incident"}


def test_prepare_rejects_schema_violation():
    validator = build_validator()
    result = prepare([INVALID_FIXTURE], validator)
    assert result.items == []
    assert len(result.failures) == 1
    path, detail = result.failures[0]
    assert path == INVALID_FIXTURE
    assert "negative_examples" in detail


def test_legacy_detection_and_wrapping():
    doc = json.loads(LEGACY_FIXTURE.read_text(encoding="utf-8"))
    assert is_legacy_term(doc) is True
    wrapped = wrap_legacy(doc)
    assert wrapped["kind"] == "new_term"
    assert wrapped["collector"] == LEGACY_COLLECTOR
    # _comment 등 밑줄 접두 메타필드는 payload에서 제외
    assert "_comment" not in wrapped["payload"]
    assert wrapped["payload"]["surface"] == "레거시테스트어"


def test_payload_format_not_treated_as_legacy():
    doc = json.loads(NEW_TERM_PAYLOAD.read_text(encoding="utf-8"))
    assert is_legacy_term(doc) is False


def test_prepare_wraps_legacy_and_passes():
    validator = build_validator()
    result = prepare([LEGACY_FIXTURE], validator)
    assert result.failures == []
    assert len(result.items) == 1
    item = result.items[0]
    assert item.kind == "new_term"
    assert item.collector == LEGACY_COLLECTOR
    expected_key = f"new_term:{normalized_key('레거시테스트어')}"
    assert item.dedup_key == expected_key


def test_dedup_key_by_kind():
    assert (
        compute_dedup_key("new_term", {"surface": "운지"})
        == f"new_term:{normalized_key('운지')}"
    )
    assert (
        compute_dedup_key("new_variant", {"variant": "운G"})
        == f"new_variant:{normalized_key('운G')}"
    )
    assert (
        compute_dedup_key("new_marker", {"name": "집게손"})
        == f"new_marker:{normalized_key('집게손')}"
    )
    assert (
        compute_dedup_key("incident", {"title": "탱크데이"})
        == f"incident:{normalized_key('탱크데이')}"
    )
    assert (
        compute_dedup_key("deprecation", {"target_surface": "사어"})
        == f"deprecation:{normalized_key('사어')}"
    )


def test_signal_score_heuristic():
    # evidence 2건 중 incident 1건 + related_incidents 1건
    payload = {
        "evidence": [
            {"evidence_type": "definition"},
            {"evidence_type": "incident"},
        ],
        "related_incidents": [{"title": "x"}],
    }
    # 2*1.0 + 1*2.0 + 1*2.0 = 6.0
    assert compute_signal_score(payload) == 6.0


def test_signal_score_capped_at_10():
    payload = {
        "evidence": [{"evidence_type": "incident"} for _ in range(10)],
        "related_incidents": [{"title": "x"} for _ in range(10)],
    }
    assert compute_signal_score(payload) == 10.0


def test_signal_score_no_evidence():
    assert compute_signal_score({}) == 0.0


def test_discover_paths_recurses_directory():
    paths = discover_paths([str(SEED_DIR)])
    names = {p.name for p in paths}
    assert "example-payload-new-term-unji.json" in names
    assert "example-payload-incident-tankday.json" in names


def test_run_dry_run_returns_zero_on_clean(capsys):
    rc = run([str(NEW_TERM_PAYLOAD)], dry_run=True, database_url=None)
    out = capsys.readouterr().out
    assert rc == 0
    assert "DRY-RUN" in out
    assert "적재 예정 1" in out


def test_run_dry_run_returns_one_on_failure(capsys):
    rc = run([str(INVALID_FIXTURE)], dry_run=True, database_url=None)
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out


def test_seed_legacy_term_unji_fails_validation_when_wrapped():
    """실제 레거시 시드(example-term-unji.json)는 negative_examples가 없어
    new_term으로 래핑하면 검증 실패한다 (해석 지점 — loader는 합성하지 않음)."""
    validator = build_validator()
    legacy = SEED_DIR / "example-term-unji.json"
    result = prepare([legacy], validator)
    assert result.items == []
    assert len(result.failures) == 1
    assert "negative_examples" in result.failures[0][1]


# ── @pytest.mark.db — 임시 DB 패턴 ──────────────────────────────────────────

DEFAULT_DATABASE_URL = "postgresql+psycopg://noise:noise@localhost:5455/noise_checker"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def _admin_dsn(database_url: str) -> str:
    """동일 서버의 기본 DB(postgres)에 접속하는 DSN."""
    base = database_url.replace("postgresql+psycopg://", "postgresql://")
    # 마지막 '/<dbname>'을 '/postgres'로 교체
    head, _, _ = base.rpartition("/")
    return f"{head}/postgres"


def _swap_dbname(database_url: str, dbname: str) -> str:
    head, _, _ = database_url.rpartition("/")
    return f"{head}/{dbname}"


@pytest.fixture()
def temp_db():
    """uuid 접미사 임시 DB 생성 → alembic upgrade head → yield URL → DROP.

    공유 noise_checker DB는 절대 건드리지 않는다.
    """
    psycopg = pytest.importorskip("psycopg")
    admin = _admin_dsn(DATABASE_URL)
    try:
        admin_conn = psycopg.connect(admin, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001 — 접속 불가 전부 skip 사유
        pytest.skip(f"DATABASE_URL 접속 불가 — DB 테스트 skip: {exc}")

    dbname = f"nc_loader_test_{uuid.uuid4().hex[:12]}"
    admin_conn.autocommit = True
    with admin_conn.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{dbname}"')
    admin_conn.close()

    temp_url = _swap_dbname(DATABASE_URL, dbname)
    env = {**os.environ, "DATABASE_URL": temp_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT, env=env, check=True, capture_output=True, text=True,
    )
    try:
        yield temp_url
    finally:
        admin_conn = psycopg.connect(admin, connect_timeout=5)
        admin_conn.autocommit = True
        with admin_conn.cursor() as cur:
            # 잔여 연결 강제 종료 후 DROP
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (dbname,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        admin_conn.close()


@pytest.mark.db
def test_insert_and_idempotent_reload(temp_db):
    """적재 → 재적재 시 dedup skip → candidate_queue 행 수 불변."""
    import psycopg

    validator = build_validator()
    result = prepare([NEW_TERM_PAYLOAD, INCIDENT_PAYLOAD], validator)
    assert result.failures == []

    inserted, skipped = insert_items(result.items, temp_db)
    assert inserted == 2
    assert skipped == 0

    # 재적재: 전부 dedup skip
    inserted2, skipped2 = insert_items(result.items, temp_db)
    assert inserted2 == 0
    assert skipped2 == 2

    dsn = temp_db.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM candidate_queue")
        assert cur.fetchone()[0] == 2
        cur.execute(
            "SELECT urgency, signal_score, dedup_key FROM candidate_queue "
            "WHERE kind = 'new_term'"
        )
        urgency, signal_score, dedup_key = cur.fetchone()
        assert urgency == "normal"
        assert dedup_key == f"new_term:{normalized_key('운지')}"
        # 운지 payload: evidence 1건(definition) → 1.0
        assert signal_score == pytest.approx(1.0)


@pytest.mark.db
def test_run_full_load_via_entrypoint(temp_db, capsys):
    """run() 전체 경로 — 적재 요약 출력 확인."""
    rc = run([str(NEW_TERM_PAYLOAD), str(INCIDENT_PAYLOAD)], dry_run=False, database_url=temp_db)
    out = capsys.readouterr().out
    assert rc == 0
    assert "적재 2" in out
