"""A program's standard length in regular semesters.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-09

Existing programs keep the usual eight (NULL); the five-year Dentistry and Pharmacy degrees set ten.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("programs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("standard_terms", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("programs", schema=None) as batch_op:
        batch_op.drop_column("standard_terms")
