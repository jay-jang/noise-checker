"""term.pattern 컬럼 추가 (term_kind='pattern' 전용 정규식 저장).

후보 payload의 "pattern"(예: '(.+)노[\\.!\\?…]*$')을 보존할 컬럼이 0001 스키마에
없어 승인 시 유실되던 문제를 고친다(M2 핫픽스 버그2 ②). nullable이며 pattern kind
항목에서만 채운다 — 다른 kind는 NULL. 빌더가 terms.json "pattern" 필드로 싣고
엔진이 컴파일한다(없으면 surface 리터럴 폴백).

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-05

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pattern: term_kind='pattern'일 때 정규식 (예: '(.+)노[\\.!\\?…]*$'). 그 외 kind는 NULL.
    op.execute("ALTER TABLE term ADD COLUMN pattern TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE term DROP COLUMN pattern")
