"""Loads the catalog from the database into memory and keeps it current.

Planning reads the whole catalog for every request, so it is held in memory.
Each request checks one integer (the catalog revision); when an import or an
admin correction bumps it, the next request reloads. This works across several
API worker processes without extra infrastructure.
"""

from __future__ import annotations

import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.catalog import Catalog, Course, Group, GroupRole, Program, Rule, parse_offered_terms
from app.domain.requisites import ParseStatus, RuleKind, from_json
from app.domain.terms import Season, Term
from app.models import (
    CatalogStateRow,
    CourseRow,
    GroupCourseRow,
    ProgramRow,
    RequirementGroupRow,
    RequisiteRuleRow,
    TermOfferingRow,
    TermScheduleRow,
)


class CatalogCache:
    def __init__(self) -> None:
        self._catalog: Catalog | None = None
        self._lock = threading.Lock()

    def get(self, session: Session) -> Catalog:
        revision = current_revision(session)
        catalog = self._catalog
        if catalog is not None and catalog.revision == revision:
            return catalog
        with self._lock:
            if self._catalog is None or self._catalog.revision != revision:
                self._catalog = load_catalog(session, revision)
            return self._catalog


def current_revision(session: Session) -> int:
    return session.scalar(select(CatalogStateRow.revision).where(CatalogStateRow.id == 1)) or 0


def load_catalog(session: Session, revision: int) -> Catalog:
    courses = {
        row.code: Course(
            code=row.code,
            title=row.title,
            units=row.units,
            description=row.description,
            component=row.component,
            notices=tuple(row.notices or ()),
            offered_terms=parse_offered_terms(row.offered_terms),
            hidden=row.hidden,
        )
        for row in session.scalars(select(CourseRow))
    }
    rules: dict[str, dict[RuleKind, Rule]] = {}
    for rule_row in session.scalars(select(RequisiteRuleRow)):
        kind = RuleKind(rule_row.kind)
        rules.setdefault(rule_row.course_code, {})[kind] = Rule(
            course=rule_row.course_code,
            kind=kind,
            source_text=rule_row.source_text,
            expr=from_json(rule_row.effective_expr),
            status=ParseStatus(rule_row.parse_status),
            reviewed=rule_row.reviewed,
            overridden=rule_row.overridden,
            id=rule_row.id,
        )

    group_rows = list(session.scalars(select(RequirementGroupRow).order_by(RequirementGroupRow.position)))
    members: dict[int, list[str]] = {}
    for member in session.scalars(select(GroupCourseRow).order_by(GroupCourseRow.position)):
        members.setdefault(member.group_id, []).append(member.course_code)
    children: dict[int | None, list[RequirementGroupRow]] = {}
    for group_row in group_rows:
        children.setdefault(group_row.parent_id, []).append(group_row)

    def build(group_row: RequirementGroupRow) -> Group:
        return Group(
            key=group_row.key,
            title=group_row.title,
            label=group_row.label,
            units_required=group_row.units_required,
            role=GroupRole(group_row.role),
            courses=tuple(members.get(group_row.id, ())),
            children=tuple(build(child) for child in children.get(group_row.id, [])),
        )

    roots = {row.program_id: row for row in children.get(None, [])}
    programs = {}
    for program_row in session.scalars(select(ProgramRow)):
        root = roots.get(program_row.id)
        if root is None:
            continue
        programs[program_row.id] = Program(
            id=program_row.id,
            name=program_row.name,
            kind=program_row.kind,
            total_units=program_row.total_units,
            root=build(root),
            catalog_year=program_row.catalog_year,
            source=program_row.source,
            source_date=program_row.source_date.isoformat() if program_row.source_date else None,
            published=program_row.published,
            hidden=program_row.hidden,
            family=program_row.family or "",
            valid_from=Term.parse(program_row.valid_from) if program_row.valid_from else None,
        )
    return Catalog(
        courses=courses, rules=rules, programs=programs, revision=revision, schedules=load_schedules(session)
    )


def load_schedules(session: Session) -> dict[Term, frozenset[str]]:
    """The course codes on each published term schedule."""
    codes: dict[int, set[str]] = {}
    offered = select(TermOfferingRow.schedule_id, TermOfferingRow.course_code)
    for schedule_id, code in session.execute(offered):
        codes.setdefault(schedule_id, set()).add(code)
    return {
        Term(row.year, Season[row.season.upper()]): frozenset(codes.get(row.id, ()))
        for row in session.scalars(select(TermScheduleRow))
    }
