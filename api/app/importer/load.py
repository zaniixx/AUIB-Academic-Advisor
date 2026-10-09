"""Write the validated course catalog and program packages to the database (F0.1, F0.3, F0.6, F0.7).

Importing is idempotent: the same files imported twice change nothing. The course
catalog is shared by every program and updated in place; it is imported first, and
each program is then checked against the courses in the database. Requisite rules
are re-parsed from the descriptions, but an admin's correction is never overwritten;
if the description it was based on changes, the rule is flagged for re-review.

Work done in the admin page wins over the files: a course edited there keeps its
values (the imported ones are stored beside it and the course is flagged when they
change), a hidden course or program stays hidden, and a program edited there is only
replaced when the import is told to (``replace_admin_edits``).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.catalog import Course, Group, Program
from app.domain.requisites import parse_description, to_json
from app.domain.terms import Season
from app.importer.package import CourseList, ProgramPackage, build_courses, build_program
from app.importer.validate import CATALOG_ID, Severity, ValidationReport, validate_courses, validate_package
from app.models import (
    AuditLogRow,
    CatalogStateRow,
    CourseRow,
    GroupCourseRow,
    ImportRunRow,
    ProgramRow,
    RequirementGroupRow,
    RequisiteRuleRow,
)
from app.services.catalog_cache import current_revision, load_catalog


@dataclass
class ImportResult:
    program_id: str
    status: str  # "imported" or "rejected"
    published: bool
    validation: ValidationReport
    counts: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "program_id": self.program_id,
            "status": self.status,
            "published": self.published,
            "counts": self.counts,
            "notes": self.notes,
            "stats": self.validation.stats,
            "findings": [asdict(f) for f in self.validation.findings],
        }


def import_courses(session: Session, course_list: CourseList, *, actor: str) -> ImportResult:
    """Validate and import the shared course catalog. The caller commits the session."""
    report = validate_courses(course_list)
    if not report.ok:
        result = ImportResult(
            CATALOG_ID, "rejected", False, report, notes=["Fix the errors and import again."]
        )
        _record(session, result, actor)
        return result
    counts: dict[str, int] = {}
    courses = build_courses(course_list)
    known = frozenset(session.scalars(select(CourseRow.code)))
    edited = frozenset(session.scalars(select(CourseRow.code).where(CourseRow.admin_edited)))
    _upsert_courses(session, courses, CATALOG_ID, counts)
    subjects = frozenset(code.split(" ")[0] for code in set(courses) | known)
    # An admin-edited course's rules follow the description the admin set, not the file's.
    sync_rules(session, {code: c for code, c in courses.items() if code not in edited}, subjects, counts)
    if any(not name.endswith("_unchanged") for name in counts):
        bump_revision(session)
    result = ImportResult(CATALOG_ID, "imported", False, report, counts)
    _record(session, result, actor)
    return result


def import_package(
    session: Session,
    package: ProgramPackage,
    *,
    actor: str,
    publish: bool | None = None,
    accept_warnings: bool = False,
    replace_admin_edits: bool = False,
) -> ImportResult:
    """Validate ``package`` against the courses in the database and import it. The caller commits."""
    session.flush()
    report = validate_package(package, load_catalog(session, current_revision(session)))
    program_id = package.meta.id
    existing = session.get(ProgramRow, program_id)
    if existing is not None and existing.admin_edited and not replace_admin_edits:
        report.add(
            Severity.ERROR,
            "program.json: id",
            "This program was edited in the admin page. Import with --replace-admin-edits to replace it.",
        )
    if not report.ok:
        result = ImportResult(
            program_id, "rejected", False, report, notes=["Fix the errors and import again."]
        )
        _record(session, result, actor)
        return result

    wants_publish = package.meta.published if publish is None else publish
    published = wants_publish and (accept_warnings or not report.warnings)
    notes = []
    if wants_publish and not published:
        notes.append("Imported but not published: review the warnings, then import with --accept-warnings.")

    hidden = existing.hidden if existing is not None else False
    program = build_program(package)
    counts = {
        "groups": write_program(
            session, program, published=published, sis_title=package.meta.sis_title, hidden=hidden
        )
    }
    bump_revision(session)

    result = ImportResult(program_id, "imported", published, report, counts, notes)
    _record(session, result, actor)
    return result


def bump_revision(session: Session) -> int:
    state = session.get(CatalogStateRow, 1)
    if state is None:
        state = CatalogStateRow(id=1, revision=0)
        session.add(state)
    state.revision += 1
    session.flush()
    return state.revision


def course_values(course: Course) -> dict[str, Any]:
    """The editable fields of a course, as stored in the database."""
    return {
        "title": course.title,
        "units": course.units,
        "description": course.description,
        "component": course.component,
        "notices": list(course.notices),
        "offered_terms": _season_names(course.offered_terms),
    }


def _upsert_courses(session: Session, courses: dict[str, Any], source: str, counts: dict[str, int]) -> None:
    existing = {
        row.code: row for row in session.scalars(select(CourseRow).where(CourseRow.code.in_(courses)))
    }
    for code, course in courses.items():
        values = course_values(course)
        row = existing.get(code)
        if row is not None and row.admin_edited:
            # The admin's values stay; the file's are kept beside them, flagged when they change.
            if row.imported_values != values:
                row.source_changed = row.imported_values is not None or any(
                    getattr(row, key) != value for key, value in values.items()
                )
                row.imported_values = values
                counts["courses_edit_kept"] = counts.get("courses_edit_kept", 0) + 1
            else:
                counts["courses_unchanged"] = counts.get("courses_unchanged", 0) + 1
            continue
        if row is None:
            session.add(CourseRow(code=code, source_program=source, **values))
            counts["courses_created"] = counts.get("courses_created", 0) + 1
        elif any(getattr(row, key) != value for key, value in values.items()):
            for key, value in values.items():
                setattr(row, key, value)
            row.source_program = source
            counts["courses_updated"] = counts.get("courses_updated", 0) + 1
        else:
            counts["courses_unchanged"] = counts.get("courses_unchanged", 0) + 1
    session.flush()


def sync_rules(
    session: Session, courses: dict[str, Any], subjects: frozenset[str], counts: dict[str, int]
) -> None:
    """Re-parse the rules of ``courses`` from their descriptions, keeping admin corrections."""
    rows: dict[str, dict[str, RequisiteRuleRow]] = {}
    for found in session.scalars(select(RequisiteRuleRow).where(RequisiteRuleRow.course_code.in_(courses))):
        rows.setdefault(found.course_code, {})[found.kind] = found

    def bump(name: str) -> None:
        counts[name] = counts.get(name, 0) + 1

    for code, course in courses.items():
        existing = rows.get(code, {})
        parsed_kinds = set()
        for parsed in parse_description(course.description, subjects):
            kind = parsed.kind.value
            parsed_kinds.add(kind)
            expr = to_json(parsed.expr)
            row = existing.get(kind)
            if row is None:
                session.add(
                    RequisiteRuleRow(
                        course_code=code,
                        kind=kind,
                        source_text=parsed.source_text,
                        parsed_expr=expr,
                        parse_status=parsed.status.value,
                        unparsed_text=parsed.unparsed_text,
                    )
                )
                bump("rules_created")
                continue
            text_changed = row.source_text != parsed.source_text
            parse_changed = row.parsed_expr != expr or row.parse_status != parsed.status.value
            if not text_changed and not parse_changed:
                bump("rules_unchanged")
                continue
            row.source_text = parsed.source_text
            row.parsed_expr = expr
            row.parse_status = parsed.status.value
            row.unparsed_text = parsed.unparsed_text
            if row.overridden:
                row.source_changed = row.source_changed or text_changed
                bump("rules_override_kept")
            else:
                row.reviewed = False
                bump("rules_updated")
        for kind, row in existing.items():
            if kind in parsed_kinds or not row.source_text:
                continue  # still in the description, or added by an admin (no source sentence)
            if row.overridden:
                row.source_changed = True
                bump("rules_override_kept")
            else:
                session.delete(row)
                bump("rules_removed")
    session.flush()


def _season_names(seasons: frozenset[Season] | None) -> list[str] | None:
    return sorted(season.name.lower() for season in seasons) if seasons else None


def write_program(
    session: Session,
    program: Program,
    *,
    published: bool,
    sis_title: str | None = None,
    origin: str = "import",
    admin_edited: bool = False,
    hidden: bool = False,
) -> int:
    """Replace the program's rows (and its requirement tree) with ``program``; returns the group count."""
    # Validation read the program tables. Drop those read-only copies, so the new rows
    # (which may reuse their ids) do not clash with them in the session.
    for loaded in list(session.identity_map.values()):
        if isinstance(loaded, ProgramRow | RequirementGroupRow | GroupCourseRow):
            session.expunge(loaded)
    # A bulk delete lets the database cascade remove the old group tree in one statement.
    session.execute(delete(ProgramRow).where(ProgramRow.id == program.id))
    session.expire_all()
    row = ProgramRow(
        id=program.id,
        name=program.name,
        kind=program.kind,
        sis_title=sis_title,
        catalog_year=program.catalog_year,
        total_units=program.total_units,
        source=program.source,
        source_date=date.fromisoformat(program.source_date) if program.source_date else None,
        published=published,
        hidden=hidden,
        origin=origin,
        admin_edited=admin_edited,
        family=program.family or None,
        valid_from=program.valid_from.label if program.valid_from else None,
    )
    session.add(row)
    session.flush()
    position = 0

    def add(group: Group, parent_id: int | None) -> None:
        nonlocal position
        group_row = RequirementGroupRow(
            program_id=program.id,
            parent_id=parent_id,
            key=group.key,
            title=group.title,
            label=group.label,
            role=group.role.value,
            units_required=group.units_required,
            position=position,
        )
        position += 1
        session.add(group_row)
        session.flush()
        for index, code in enumerate(dict.fromkeys(group.courses)):
            session.add(GroupCourseRow(group_id=group_row.id, course_code=code, position=index))
        for child in group.children:
            add(child, group_row.id)

    add(program.root, None)
    session.flush()
    return position


def _record(session: Session, result: ImportResult, actor: str) -> None:
    summary = result.summary()
    session.add(
        ImportRunRow(
            program_id=result.program_id,
            status=result.status,
            published=result.published,
            actor=actor,
            report=summary,
        )
    )
    session.add(
        AuditLogRow(
            actor=actor,
            action=f"{'catalog' if result.program_id == CATALOG_ID else 'program'}.import.{result.status}",
            target=result.program_id,
            detail={
                "published": result.published,
                "counts": result.counts,
                "errors": len(result.validation.errors),
                "warnings": len([f for f in result.validation.findings if f.severity is Severity.WARNING]),
            },
        )
    )
    session.flush()
