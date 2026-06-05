"""릴리스 빌더 v1 테스트 (M2-A).

순수 로직(버전 규칙·kiwi 사전 구성)은 DB 없이 검증한다.
빌드 통합(@pytest.mark.db)은 test_console_core.py와 동일한 **임시 DB 패턴**으로 격리한다:
  DATABASE_URL 서버에 uuid 접미사 임시 DB를 CREATE → alembic upgrade head → 테스트 → DROP.
  공유 noise_checker DB·docker compose는 절대 건드리지 않는다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from noise_checker.normalizer import NORMALIZER_VERSION, normalize
from noise_checker.release_builder import build_release, next_version

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql+psycopg://noise:noise@localhost:5455/noise_checker"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


# ===========================================================================
# 순수 로직 — DB 불필요
# ===========================================================================
class TestNextVersion:
    def test_first_of_day(self, tmp_path):
        assert next_version(tmp_path, today="2026.06.05") == "2026.06.05-1"

    def test_increments_within_day(self, tmp_path):
        (tmp_path / "2026.06.05-1").mkdir()
        (tmp_path / "2026.06.05-2").mkdir()
        assert next_version(tmp_path, today="2026.06.05") == "2026.06.05-3"

    def test_ignores_other_days_and_nonversion_dirs(self, tmp_path):
        (tmp_path / "2026.06.04-9").mkdir()
        (tmp_path / "not-a-version").mkdir()
        (tmp_path / "2026.06.05-1").mkdir()
        assert next_version(tmp_path, today="2026.06.05") == "2026.06.05-2"

    def test_missing_dir(self, tmp_path):
        assert next_version(tmp_path / "nope", today="2026.06.05") == "2026.06.05-1"


# ===========================================================================
# 빌드 통합 — 임시 DB 격리 (@pytest.mark.db)
# ===========================================================================
db = pytest.mark.db


def _alembic_upgrade(db_url: str) -> None:
    env = {**os.environ, "DATABASE_URL": db_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT, env=env, check=True, capture_output=True, text=True,
    )


@pytest.fixture(scope="module")
def temp_db_url():
    """임시 데이터베이스를 만들고 alembic upgrade 후 URL을 준다 (DROP까지 책임)."""
    psycopg = pytest.importorskip("psycopg")

    base = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    head, _, _olddb = base.rpartition("/")
    admin_dsn = f"{head}/postgres"
    temp_name = f"nc_relbuild_test_{uuid.uuid4().hex[:12]}"

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

    try:
        yield temp_url
    finally:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (temp_name,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{temp_name}"')
        admin.close()


@pytest.fixture
def seeded_db_url(temp_db_url):
    """표본 term 3건을 적재한다.

      ① active 'A운지' (deceased) — verified 음절형 변형 1 + 미검증 변형 1(제외) +
         jamo 변형 1(kiwi 제외) + active composite_rule 1.
      ② watchlist 'B워치' — safe_contexts 보유.
      ③ active 'C내부' but release_policy='internal_only' — 빌드에서 제외되어야 함.
    """
    import sqlalchemy
    from sqlalchemy import text

    engine = sqlalchemy.create_engine(temp_db_url, poolclass=sqlalchemy.pool.NullPool)
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE composite_rule, term_category, term_variant, term_evidence, "
            "term, source RESTART IDENTITY CASCADE"
        ))
        sid = conn.execute(text(
            "INSERT INTO source (title, source_type, license_class) "
            "VALUES ('테스트 출처', 'internal', 'permissive') RETURNING id"
        )).scalar()

        # ① active term (draft로 INSERT 후 evidence 추가 → active 전환: 게이트 통과)
        t1 = conn.execute(text(
            "INSERT INTO term (surface, normalized_key, term_kind, origin_story, meaning, "
            "severity, ambiguity, safe_contexts, status, release_policy) "
            "VALUES ('A운지', :nk, 'word', '유래', '의미', 5, 'ambiguous', "
            "ARRAY['버섯','운지버섯'], 'draft', 'general') RETURNING id"
        ), {"nk": normalize("A운지")[0]}).scalar()
        conn.execute(text(
            "INSERT INTO term_evidence (term_id, source_id, evidence_type, added_by) "
            "VALUES (:t, :s, 'origin', 'test')"
        ), {"t": t1, "s": sid})
        conn.execute(text("UPDATE term SET status='active' WHERE id=:t"), {"t": t1})
        # 카테고리
        conn.execute(text(
            "INSERT INTO term_category (term_id, category_id) "
            "SELECT :t, id FROM category WHERE code='deceased'"
        ), {"t": t1})
        # verified 음절형 변형 (kiwi 포함 대상)
        conn.execute(text(
            "INSERT INTO term_variant (term_id, variant, variant_kind, normalized_key, verified) "
            "VALUES (:t, 'A운G', 'leet', :nk, true)"
        ), {"t": t1, "nk": normalize("A운G")[0]})
        # verified jamo 변형 (release 포함, kiwi 제외 대상)
        conn.execute(text(
            "INSERT INTO term_variant (term_id, variant, variant_kind, normalized_key, verified) "
            "VALUES (:t, 'ㅇㅈ', 'chosung', :nk, true)"
        ), {"t": t1, "nk": normalize("ㅇㅈ")[0]})
        # 미검증 변형 (release 제외 대상)
        conn.execute(text(
            "INSERT INTO term_variant (term_id, variant, variant_kind, normalized_key, verified) "
            "VALUES (:t, 'A운지미검증', 'leet', :nk, false)"
        ), {"t": t1, "nk": normalize("A운지미검증")[0]})
        # active composite_rule
        conn.execute(text(
            "INSERT INTO composite_rule (primary_term_id, trigger_kind, trigger_pattern, "
            "base_severity, severity_delta, status) "
            "VALUES (:t, 'date_context', '5\\.23', 1, 3, 'active')"
        ), {"t": t1})

        # ② watchlist term
        conn.execute(text(
            "INSERT INTO term (surface, normalized_key, term_kind, origin_story, meaning, "
            "severity, safe_contexts, status, release_policy) "
            "VALUES ('B워치', :nk, 'word', '유래', '의미', 2, ARRAY['관찰'], "
            "'watchlist', 'general')"
        ), {"nk": normalize("B워치")[0]})

        # ③ active term이지만 internal_only → 제외
        t3 = conn.execute(text(
            "INSERT INTO term (surface, normalized_key, term_kind, origin_story, meaning, "
            "severity, status, release_policy) "
            "VALUES ('C내부', :nk, 'word', '유래', '의미', 4, 'draft', 'internal_only') "
            "RETURNING id"
        ), {"nk": normalize("C내부")[0]}).scalar()
        conn.execute(text(
            "INSERT INTO term_evidence (term_id, source_id, evidence_type, added_by) "
            "VALUES (:t, :s, 'origin', 'test')"
        ), {"t": t3, "s": sid})
        conn.execute(text("UPDATE term SET status='active' WHERE id=:t"), {"t": t3})

    engine.dispose()
    return temp_db_url


@db
def test_build_manifest_counts_and_checksums(seeded_db_url, tmp_path):
    manifest = build_release(seeded_db_url, tmp_path, version="2026.06.05-1")

    # internal_only(C내부) 제외 → active(A운지) + watchlist(B워치) = 2건
    assert manifest["term_count"] == 2
    # verified 변형만 (A운G, ㅇㅈ) = 2; 미검증 'A운지미검증'은 제외
    assert manifest["variant_count"] == 2
    assert manifest["release_version"] == "2026.06.05-1"
    assert manifest["normalizer_code_version"] == NORMALIZER_VERSION

    release_dir = tmp_path / "2026.06.05-1"
    # 체크섬이 실제 파일과 일치
    import hashlib
    for fname in ("terms.json", "kiwi_user_dict.tsv"):
        actual = hashlib.sha256((release_dir / fname).read_bytes()).hexdigest()
        assert manifest["checksums"][fname] == actual


@db
def test_terms_json_content(seeded_db_url, tmp_path):
    build_release(seeded_db_url, tmp_path, version="2026.06.05-1")
    terms = json.loads((tmp_path / "2026.06.05-1" / "terms.json").read_text())

    by_surface = {t["surface"]: t for t in terms}
    assert set(by_surface) == {"A운지", "B워치"}  # internal_only 제외

    active = by_surface["A운지"]
    # normalized_key는 normalize()로 재생성
    assert active["normalized_key"] == normalize("A운지")[0]
    assert active["severity"] == 5
    assert active["ambiguity"] == "ambiguous"
    assert active["status"] == "active"
    assert active["categories"] == ["deceased"]
    assert active["safe_contexts"] == ["버섯", "운지버섯"]
    assert active["is_dogwhistle_marker"] is False
    # verified 변형 2건만 (미검증 제외), normalized_key 재생성
    vsurfaces = {v["surface"] for v in active["variants"]}
    assert vsurfaces == {"A운G", "ㅇㅈ"}
    for v in active["variants"]:
        assert v["normalized_key"] == normalize(v["surface"])[0]
    # active composite_rule 1건
    assert len(active["combination_rules"]) == 1
    assert active["combination_rules"][0]["trigger_kind"] == "date_context"

    watch = by_surface["B워치"]
    assert watch["status"] == "watchlist"
    assert watch["safe_contexts"] == ["관찰"]
    assert watch["variants"] == []


@db
def test_kiwi_dict_lines(seeded_db_url, tmp_path):
    build_release(seeded_db_url, tmp_path, version="2026.06.05-1")
    lines = (tmp_path / "2026.06.05-1" / "kiwi_user_dict.tsv").read_text().splitlines()

    forms = {ln.split("\t")[0] for ln in lines}
    # active surface + 음절형 verified 변형(A운G)만. jamo/chosung(ㅇㅈ) 제외.
    assert forms == {"A운지", "A운G"}
    # watchlist surface(B워치)·미검증 변형·internal_only는 미포함
    assert "B워치" not in forms
    assert "C내부" not in forms
    assert "ㅇㅈ" not in forms
    # 형식: form<TAB>NNP<TAB>score
    for ln in lines:
        parts = ln.split("\t")
        assert len(parts) == 3
        assert parts[1] == "NNP"


@db
def test_kiwi_dict_loads_in_kiwipiepy(seeded_db_url, tmp_path):
    """생성된 사전이 실제 kiwipiepy에 로드되어 형태소 경계를 보강하는지 확인."""
    kiwipiepy = pytest.importorskip("kiwipiepy")
    build_release(seeded_db_url, tmp_path, version="2026.06.05-1")
    dict_path = tmp_path / "2026.06.05-1" / "kiwi_user_dict.tsv"

    kiwi = kiwipiepy.Kiwi()
    added = kiwi.load_user_dictionary(str(dict_path))
    assert added >= 1
