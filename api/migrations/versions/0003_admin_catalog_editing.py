"""Admin editing of the catalog, hidden courses and programs, and term schedules.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09

Courses and programs can be hidden and edited in the admin page; an import keeps
those edits. Term schedules (the courses offered in a term) are new tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("courses", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("admin_edited", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("imported_values", JSONType, nullable=True))
        batch_op.add_column(
            sa.Column("source_changed", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("programs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("origin", sa.String(length=16), nullable=False, server_default="import"))
        batch_op.add_column(sa.Column("admin_edited", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "term_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("season", sa.String(length=8), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", "season", name="uq_schedule_term"),
    )
    op.create_table(
        "term_offerings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("course_code", sa.String(length=16), nullable=False),
        sa.Column("section", sa.String(length=20), nullable=False),
        sa.Column("days", sa.String(length=40), nullable=False),
        sa.Column("time", sa.String(length=40), nullable=False),
        sa.Column("instructor", sa.String(length=120), nullable=False),
        sa.Column("room", sa.String(length=60), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["schedule_id"], ["term_schedules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_code"], ["courses.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_term_offerings_schedule_id", "term_offerings", ["schedule_id"])
    op.create_index("ix_term_offerings_course_code", "term_offerings", ["course_code"])


def downgrade() -> None:
    op.drop_index("ix_term_offerings_course_code", table_name="term_offerings")
    op.drop_index("ix_term_offerings_schedule_id", table_name="term_offerings")
    op.drop_table("term_offerings")
    op.drop_table("term_schedules")
    with op.batch_alter_table("programs", schema=None) as batch_op:
        batch_op.drop_column("admin_edited")
        batch_op.drop_column("origin")
        batch_op.drop_column("hidden")
    with op.batch_alter_table("courses", schema=None) as batch_op:
        batch_op.drop_column("source_changed")
        batch_op.drop_column("imported_values")
        batch_op.drop_column("admin_edited")
        batch_op.drop_column("hidden")
