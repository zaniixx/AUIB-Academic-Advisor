"""Program versions: a family shared by the versions of a program, and the term each applies from.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09

Existing programs become the only version of their own family, applying from the start (F0.4).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("programs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("family", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("valid_from", sa.String(length=20), nullable=True))
        batch_op.create_index("ix_programs_family", ["family"])


def downgrade() -> None:
    with op.batch_alter_table("programs", schema=None) as batch_op:
        batch_op.drop_index("ix_programs_family")
        batch_op.drop_column("valid_from")
        batch_op.drop_column("family")
