"""Courses record the seasons they run in; CS internships run in summer only.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08

Adds courses.offered_terms (NULL = every regular term) and fixes existing data so
databases imported before this change plan internships in summer without a re-import.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUMMER_ONLY = ("CSC 390", "CSC 391")
JSONType = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("courses", schema=None) as batch_op:
        batch_op.add_column(sa.Column("offered_terms", JSONType, nullable=True))

    courses = sa.table("courses", sa.column("code", sa.String), sa.column("offered_terms", JSONType))
    op.execute(courses.update().where(courses.c.code.in_(SUMMER_ONLY)).values(offered_terms=["summer"]))
    state = sa.table("catalog_state", sa.column("id", sa.Integer), sa.column("revision", sa.Integer))
    op.execute(state.update().where(state.c.id == 1).values(revision=state.c.revision + 1))


def downgrade() -> None:
    with op.batch_alter_table("courses", schema=None) as batch_op:
        batch_op.drop_column("offered_terms")
