"""Database tables.

Only catalog data and admin records are stored. Guest course histories and
plans are never written to the database (F11.5); accounts and saved plans
arrive with sign-in (F9) in a later migration.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class CourseRow(Base):
    __tablename__ = "courses"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    units: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text, default="")
    component: Mapped[str | None] = mapped_column(String(60))
    notices: Mapped[list[str]] = mapped_column(JSONType, default=list)
    # Seasons the course runs in (["summer"] for internships); NULL means every regular term.
    offered_terms: Mapped[list[str] | None] = mapped_column(JSONType, nullable=True)
    source_program: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    rules: Mapped[list[RequisiteRuleRow]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class RequisiteRuleRow(Base):
    """A course's prerequisite or corequisite rule, as parsed and as corrected by an admin (F0.2, F0.3)."""

    __tablename__ = "requisite_rules"
    __table_args__ = (UniqueConstraint("course_code", "kind", name="uq_rule_course_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_code: Mapped[str] = mapped_column(ForeignKey("courses.code", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    source_text: Mapped[str] = mapped_column(Text)
    parsed_expr: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    parse_status: Mapped[str] = mapped_column(String(16), index=True)
    unparsed_text: Mapped[str] = mapped_column(Text, default="")
    override_expr: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    override_is_none: Mapped[bool] = mapped_column(Boolean, default=False)  # admin decided: no requisite
    override_note: Mapped[str | None] = mapped_column(Text)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    course: Mapped[CourseRow] = relationship(back_populates="rules")

    @property
    def overridden(self) -> bool:
        return self.override_expr is not None or self.override_is_none

    @property
    def effective_expr(self) -> dict[str, Any] | None:
        if self.override_is_none:
            return None
        return self.override_expr if self.override_expr is not None else self.parsed_expr


class ProgramRow(Base):
    __tablename__ = "programs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16))
    sis_title: Mapped[str | None] = mapped_column(String(300))
    catalog_year: Mapped[str | None] = mapped_column(String(20))
    total_units: Mapped[float] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(300))
    source_date: Mapped[date | None] = mapped_column(Date)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    groups: Mapped[list[RequirementGroupRow]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RequirementGroupRow.position",
    )


class RequirementGroupRow(Base):
    __tablename__ = "requirement_groups"
    __table_args__ = (UniqueConstraint("program_id", "key", name="uq_group_program_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("requirement_groups.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(300))
    label: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(32))
    units_required: Mapped[float] = mapped_column(Float)
    position: Mapped[int] = mapped_column(Integer)

    program: Mapped[ProgramRow] = relationship(back_populates="groups")
    courses: Mapped[list[GroupCourseRow]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="GroupCourseRow.position"
    )


class GroupCourseRow(Base):
    __tablename__ = "group_courses"

    group_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_groups.id", ondelete="CASCADE"), primary_key=True
    )
    course_code: Mapped[str] = mapped_column(ForeignKey("courses.code", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)


class ImportRunRow(Base):
    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    program_id: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(16))  # imported, rejected
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    actor: Mapped[str] = mapped_column(String(120))
    report: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class AuditLogRow(Base):
    """Every admin action (F9.3)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(60))
    target: Mapped[str] = mapped_column(String(200))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class CatalogStateRow(Base):
    """A single row whose revision goes up whenever catalog data changes, so every API worker reloads."""

    __tablename__ = "catalog_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
