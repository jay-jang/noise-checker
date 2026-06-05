"""초기 전체 스키마 (docs/02-database-design.md v3 + docs/04 §3 candidate_queue).

raw SQL(op.execute)로 02 §3.1~3.10 전 테이블 + candidate_queue + active 게이트 트리거 +
category 시드를 생성한다. downgrade는 역순 DROP.

Revision ID: 0001
Revises:
Create Date: 2026-06-05

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 3.1 source ----------------------------------------------------------
    op.execute("""
    CREATE TABLE source (
        id            BIGSERIAL PRIMARY KEY,
        url           TEXT UNIQUE,
        title         TEXT NOT NULL,
        source_type   TEXT NOT NULL CHECK (source_type IN (
                        'dataset','wiki','news','academic','community','government','internal'
                      )),
        publisher     TEXT,
        published_at  DATE,
        retrieved_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        license       TEXT,
        license_class TEXT NOT NULL DEFAULT 'unknown' CHECK (license_class IN (
                        'permissive','share_alike','noncommercial','no_derivatives',
                        'restricted','unknown'
                      )),
        reliability   SMALLINT NOT NULL DEFAULT 3
                      CHECK (reliability BETWEEN 1 AND 5),
        archive_url   TEXT,
        snapshot_path TEXT,
        notes         TEXT
    )
    """)

    # 3.2 term ------------------------------------------------------------
    op.execute("""
    CREATE TABLE term (
        id              BIGSERIAL PRIMARY KEY,
        surface         TEXT NOT NULL,
        normalized_key  TEXT NOT NULL,
        term_kind       TEXT NOT NULL CHECK (term_kind IN ('word','phrase','pattern','number')),
        origin_community TEXT,
        origin_story    TEXT NOT NULL,
        origin_period   TEXT,
        meaning         TEXT NOT NULL,
        severity        SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5),
        ambiguity       TEXT NOT NULL DEFAULT 'unambiguous' CHECK (ambiguity IN (
                          'unambiguous','ambiguous','common'
                        )),
        safe_contexts   TEXT[],
        status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
                          'draft','watchlist','in_review','active','deprecated','rejected'
                        )),
        release_policy  TEXT NOT NULL DEFAULT 'general' CHECK (release_policy IN (
                          'general','advisory_only','internal_only','hold_legal'
                        )),
        provenance_class TEXT NOT NULL DEFAULT 'internal' CHECK (provenance_class IN (
                          'permissive_core','share_alike_core','restricted_eval_only','internal'
                        )),
        first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (normalized_key, term_kind)
    )
    """)
    op.execute("CREATE INDEX idx_term_status ON term(status)")
    op.execute("CREATE INDEX idx_term_nkey   ON term(normalized_key)")

    # 3.3 term_evidence ---------------------------------------------------
    op.execute("""
    CREATE TABLE term_evidence (
        term_id     BIGINT NOT NULL REFERENCES term(id) ON DELETE CASCADE,
        source_id   BIGINT NOT NULL REFERENCES source(id),
        evidence_type TEXT NOT NULL CHECK (evidence_type IN (
                      'origin','usage','incident','definition'
                    )),
        excerpt     TEXT CHECK (char_length(excerpt) <= 300),
        added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        added_by    TEXT NOT NULL,
        PRIMARY KEY (term_id, source_id, evidence_type)
    )
    """)

    # 3.4 term_variant ----------------------------------------------------
    op.execute("""
    CREATE TABLE term_variant (
        id             BIGSERIAL PRIMARY KEY,
        term_id        BIGINT NOT NULL REFERENCES term(id) ON DELETE CASCADE,
        variant        TEXT NOT NULL,
        variant_kind   TEXT NOT NULL CHECK (variant_kind IN (
                         'jamo','leet','chosung','yamin','translit','spacing','regex'
                       )),
        pattern        TEXT,
        normalized_key TEXT NOT NULL,
        auto_generated BOOLEAN NOT NULL DEFAULT false,
        verified       BOOLEAN NOT NULL DEFAULT false,
        UNIQUE (term_id, variant)
    )
    """)

    # 3.5 category + term_category ---------------------------------------
    op.execute("""
    CREATE TABLE category (
        id    SERIAL PRIMARY KEY,
        code  TEXT UNIQUE NOT NULL,
        label TEXT NOT NULL,
        description TEXT
    )
    """)
    op.execute("""
    CREATE TABLE term_category (
        term_id     BIGINT REFERENCES term(id) ON DELETE CASCADE,
        category_id INT REFERENCES category(id),
        PRIMARY KEY (term_id, category_id)
    )
    """)

    # 3.6 image_marker + reference + evidence -----------------------------
    op.execute("""
    CREATE TABLE image_marker (
        id              BIGSERIAL PRIMARY KEY,
        name            TEXT NOT NULL,
        marker_kind     TEXT NOT NULL CHECK (marker_kind IN (
                          'hand_sign','logo','meme_image','watermark','symbol'
                        )),
        origin_community TEXT,
        origin_story    TEXT NOT NULL,
        severity        SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5),
        detection_method TEXT[] NOT NULL,
        status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN
                          ('draft','watchlist','in_review','active','deprecated','rejected')),
        release_policy  TEXT NOT NULL DEFAULT 'advisory_only' CHECK (release_policy IN
                          ('general','advisory_only','internal_only','hold_legal')),
        provenance_class TEXT NOT NULL DEFAULT 'internal' CHECK (provenance_class IN
                          ('permissive_core','share_alike_core','restricted_eval_only','internal')),
        first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """)
    op.execute("""
    CREATE TABLE marker_reference_image (
        id          BIGSERIAL PRIMARY KEY,
        marker_id   BIGINT NOT NULL REFERENCES image_marker(id) ON DELETE CASCADE,
        storage_path TEXT NOT NULL,
        phash       BIT(64),
        clip_embedding vector(512),
        source_id   BIGINT REFERENCES source(id),
        license_ok  BOOLEAN NOT NULL DEFAULT false,
        notes       TEXT
    )
    """)
    op.execute("""
    CREATE TABLE marker_evidence (
        marker_id   BIGINT NOT NULL REFERENCES image_marker(id) ON DELETE CASCADE,
        source_id   BIGINT NOT NULL REFERENCES source(id),
        evidence_type TEXT NOT NULL CHECK (evidence_type IN (
                      'origin','usage','incident','definition'
                    )),
        excerpt     TEXT CHECK (char_length(excerpt) <= 300),
        added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        added_by    TEXT NOT NULL,
        PRIMARY KEY (marker_id, source_id, evidence_type)
    )
    """)

    # 3.7 incident --------------------------------------------------------
    op.execute("""
    CREATE TABLE incident (
        id          BIGSERIAL PRIMARY KEY,
        title       TEXT NOT NULL,
        display_title TEXT,
        occurred_at DATE,
        description TEXT NOT NULL,
        medium      TEXT CHECK (medium IN ('ad','broadcast','game','product','sns','app','other')),
        term_id     BIGINT REFERENCES term(id),
        marker_id   BIGINT REFERENCES image_marker(id),
        source_id   BIGINT NOT NULL REFERENCES source(id),
        sample_text TEXT,
        legal_reviewed BOOLEAN NOT NULL DEFAULT false,
        disclosable    BOOLEAN NOT NULL DEFAULT false,
        CHECK (term_id IS NOT NULL OR marker_id IS NOT NULL)
    )
    """)

    # 3.8 composite_rule --------------------------------------------------
    op.execute("""
    CREATE TABLE composite_rule (
        id              BIGSERIAL PRIMARY KEY,
        primary_term_id BIGINT NOT NULL REFERENCES term(id),
        trigger_kind    TEXT NOT NULL CHECK (trigger_kind IN (
                          'co_occurrence','date_context','amount_context','time_context','proximity'
                        )),
        trigger_terms   BIGINT[],
        trigger_pattern TEXT,
        proximity_window INT,
        base_severity   SMALLINT NOT NULL,
        severity_delta  SMALLINT NOT NULL,
        status          TEXT NOT NULL DEFAULT 'draft' CHECK (status IN
                          ('draft','in_review','active','deprecated','rejected')),
        notes           TEXT
    )
    """)

    # 3.9 review_log ------------------------------------------------------
    op.execute("""
    CREATE TABLE review_log (
        id          BIGSERIAL PRIMARY KEY,
        entity_type TEXT NOT NULL CHECK (entity_type IN ('term','image_marker','variant')),
        entity_id   BIGINT NOT NULL,
        action      TEXT NOT NULL,
        old_value   JSONB,
        new_value   JSONB,
        reviewer    TEXT NOT NULL,
        reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        rationale   TEXT
    )
    """)

    # 3.10 dictionary_release --------------------------------------------
    op.execute("""
    CREATE TABLE dictionary_release (
        id           BIGSERIAL PRIMARY KEY,
        version      TEXT UNIQUE NOT NULL,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        term_count   INT NOT NULL,
        variant_count INT NOT NULL,
        marker_count INT NOT NULL,
        artifact_path TEXT NOT NULL,
        effective_license TEXT NOT NULL,
        changelog    TEXT,
        released_by  TEXT NOT NULL
    )
    """)

    # docs/04 §3 candidate_queue -----------------------------------------
    op.execute("""
    CREATE TABLE candidate_queue (
        id           BIGSERIAL PRIMARY KEY,
        payload      JSONB NOT NULL,
        kind         TEXT NOT NULL,
        collector    TEXT NOT NULL,
        signal_score REAL NOT NULL,
        urgency      TEXT NOT NULL DEFAULT 'normal',
        dedup_key    TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'pending',
        created_at   TIMESTAMPTZ DEFAULT now(),
        UNIQUE (dedup_key, kind)
    )
    """)

    # active 게이트 트리거 (02 §3.2/§3.6 주석 사양) -----------------------
    # ① BEFORE INSERT OR UPDATE OF status: active 전이 시 origin/definition evidence ≥ 1
    # ③ watchlist→active 직접 전이 차단 (in_review 경유 필수)
    op.execute("""
    CREATE OR REPLACE FUNCTION enforce_term_active_gate() RETURNS trigger AS $$
    BEGIN
        IF NEW.status = 'active' THEN
            -- ③ watchlist에서 active로 직접 전이 차단 (UPDATE에서만 OLD 존재)
            IF TG_OP = 'UPDATE' AND OLD.status = 'watchlist' THEN
                RAISE EXCEPTION
                  'watchlist는 active 직접 전이 불가 (in_review 경유 필수): term %', NEW.id;
            END IF;
            -- ① origin/definition evidence ≥ 1 강제
            IF NOT EXISTS (
                SELECT 1 FROM term_evidence te
                WHERE te.term_id = NEW.id
                  AND te.evidence_type IN ('origin','definition')
            ) THEN
                RAISE EXCEPTION
                  'active 전이 불가: term %는 origin/definition evidence가 없습니다', NEW.id;
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER trg_term_active_gate
        BEFORE INSERT OR UPDATE OF status ON term
        FOR EACH ROW EXECUTE FUNCTION enforce_term_active_gate()
    """)

    # ② active 상태인 term의 마지막 origin/definition evidence DELETE 차단
    op.execute("""
    CREATE OR REPLACE FUNCTION enforce_term_evidence_retention() RETURNS trigger AS $$
    DECLARE
        term_status TEXT;
    BEGIN
        IF OLD.evidence_type IN ('origin','definition') THEN
            SELECT status INTO term_status FROM term WHERE id = OLD.term_id;
            IF term_status = 'active' AND NOT EXISTS (
                SELECT 1 FROM term_evidence te
                WHERE te.term_id = OLD.term_id
                  AND te.evidence_type IN ('origin','definition')
                  AND NOT (te.term_id = OLD.term_id
                           AND te.source_id = OLD.source_id
                           AND te.evidence_type = OLD.evidence_type)
            ) THEN
                RAISE EXCEPTION
                  'active term %의 마지막 origin/definition evidence 삭제 불가', OLD.term_id;
            END IF;
        END IF;
        RETURN OLD;
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER trg_term_evidence_retention
        BEFORE DELETE ON term_evidence
        FOR EACH ROW EXECUTE FUNCTION enforce_term_evidence_retention()
    """)

    # image_marker 공통 게이트 (marker_evidence 기준) ---------------------
    op.execute("""
    CREATE OR REPLACE FUNCTION enforce_marker_active_gate() RETURNS trigger AS $$
    BEGIN
        IF NEW.status = 'active' THEN
            IF TG_OP = 'UPDATE' AND OLD.status = 'watchlist' THEN
                RAISE EXCEPTION
                  'watchlist는 active 직접 전이 불가 (in_review 경유 필수): marker %', NEW.id;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM marker_evidence me
                WHERE me.marker_id = NEW.id
                  AND me.evidence_type IN ('origin','definition')
            ) THEN
                RAISE EXCEPTION
                  'active 전이 불가: image_marker %에 origin/definition evidence 없음', NEW.id;
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER trg_marker_active_gate
        BEFORE INSERT OR UPDATE OF status ON image_marker
        FOR EACH ROW EXECUTE FUNCTION enforce_marker_active_gate()
    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION enforce_marker_evidence_retention() RETURNS trigger AS $$
    DECLARE
        marker_status TEXT;
    BEGIN
        IF OLD.evidence_type IN ('origin','definition') THEN
            SELECT status INTO marker_status FROM image_marker WHERE id = OLD.marker_id;
            IF marker_status = 'active' AND NOT EXISTS (
                SELECT 1 FROM marker_evidence me
                WHERE me.marker_id = OLD.marker_id
                  AND me.evidence_type IN ('origin','definition')
                  AND NOT (me.marker_id = OLD.marker_id
                           AND me.source_id = OLD.source_id
                           AND me.evidence_type = OLD.evidence_type)
            ) THEN
                RAISE EXCEPTION
                  'active image_marker %의 마지막 origin/definition evidence는 삭제할 수 없습니다',
                  OLD.marker_id;
            END IF;
        END IF;
        RETURN OLD;
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER trg_marker_evidence_retention
        BEFORE DELETE ON marker_evidence
        FOR EACH ROW EXECUTE FUNCTION enforce_marker_evidence_retention()
    """)

    # category 시드 (data/schema/candidate-term.schema.json categories enum과 일치) -
    op.execute("""
    INSERT INTO category (code, label) VALUES
        ('misogyny',         '여성혐오'),
        ('misandry',         '남성혐오'),
        ('region_hate',      '지역비하'),
        ('deceased',         '고인비하'),
        ('disability',       '장애비하'),
        ('race_nation',      '인종/국적 비하'),
        ('politics',         '정치 혐오'),
        ('sexual_minority',  '성소수자 비하'),
        ('age',              '연령 비하'),
        ('religion',         '종교 비하'),
        ('community_jargon', '커뮤니티 은어')
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_marker_evidence_retention ON marker_evidence")
    op.execute("DROP FUNCTION IF EXISTS enforce_marker_evidence_retention()")
    op.execute("DROP TRIGGER IF EXISTS trg_marker_active_gate ON image_marker")
    op.execute("DROP FUNCTION IF EXISTS enforce_marker_active_gate()")
    op.execute("DROP TRIGGER IF EXISTS trg_term_evidence_retention ON term_evidence")
    op.execute("DROP FUNCTION IF EXISTS enforce_term_evidence_retention()")
    op.execute("DROP TRIGGER IF EXISTS trg_term_active_gate ON term")
    op.execute("DROP FUNCTION IF EXISTS enforce_term_active_gate()")

    op.execute("DROP TABLE IF EXISTS candidate_queue")
    op.execute("DROP TABLE IF EXISTS dictionary_release")
    op.execute("DROP TABLE IF EXISTS review_log")
    op.execute("DROP TABLE IF EXISTS composite_rule")
    op.execute("DROP TABLE IF EXISTS incident")
    op.execute("DROP TABLE IF EXISTS marker_evidence")
    op.execute("DROP TABLE IF EXISTS marker_reference_image")
    op.execute("DROP TABLE IF EXISTS image_marker")
    op.execute("DROP TABLE IF EXISTS term_category")
    op.execute("DROP TABLE IF EXISTS category")
    op.execute("DROP TABLE IF EXISTS term_variant")
    op.execute("DROP TABLE IF EXISTS term_evidence")
    op.execute("DROP TABLE IF EXISTS term")
    op.execute("DROP TABLE IF EXISTS source")
    # vector 확장은 DROP하지 않음 (다른 객체가 의존할 수 있고, 재설치 비용 회피)
