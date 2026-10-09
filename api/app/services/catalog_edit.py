"""Changes an admin makes to the catalog in the admin page: courses, programs and term schedules.

Every change is written to the audit log and raises the catalog revision, so each API
worker plans with it on its next request. How these edits survive a later import of the
course files is explained in ``app.models`` and ``app.importer.load``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.catalog import OFFERED_TERM_NAMES, Course, Program
from app.domain.codes import normalize_code
from app.domain.terms import Term
from app.importer.load import bump_revision, sync_rules, write_program
from app.importer.tables import Table, TableRow
from app.importer.validate import ADMIN_FORM, ValidationReport, validate_program
from app.models import (
    AuditLogRow,
    CourseRow,
    ProgramRow,
    TermOfferingRow,
    TermScheduleRow,
)
from app.services.catalog_cache import current_revision, load_catalog

ADMIN_SOURCE = "admin"
FIELDS = ("title", "units", "description", "component", "notices", "offered_terms")
# How a field is named to an admin (AUIB counts course load in credits).
FIELD_NAMES = {"units": "credits", "offered_terms": "runs in"}


class EditError(ValueError):
    """The change cannot be made as asked (the message says why)."""


def audit(session: Session, actor: str, action: str, target: str, detail: dict[str, Any]) -> None:
    session.add(AuditLogRow(actor=actor, action=action, target=target, detail=detail))


def row_values(row: CourseRow) -> dict[str, Any]:
    return {name: getattr(row, name) for name in FIELDS}


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


def create_course(
    session: Session, code: str, values: dict[str, Any], actor: str, *, hidden: bool = False, log: bool = True
) -> CourseRow:
    if session.get(CourseRow, code) is not None:
        raise EditError(f"{code} is already in the catalog; edit it instead")
    row = CourseRow(code=code, source_program=ADMIN_SOURCE, admin_edited=True, hidden=hidden, **values)
    session.add(row)
    session.flush()
    _sync_rules(session, [row])
    if log:
        audit(session, actor, "course.create", code, {"values": values, "hidden": hidden})
        bump_revision(session)
    return row


def update_course(
    session: Session, row: CourseRow, values: dict[str, Any], actor: str, *, log: bool = True
) -> dict[str, list[Any]]:
    """Apply ``values``; returns the fields that changed as {field: [before, after]}."""
    before = row_values(row)
    changes = {name: [before[name], values[name]] for name in FIELDS if before[name] != values[name]}
    if not changes:
        return {}
    if not row.admin_edited and row.source_program != ADMIN_SOURCE:
        row.imported_values = before  # so the edit can be undone
    row.admin_edited = True
    for name, (_old, new) in changes.items():
        setattr(row, name, new)
    session.flush()
    if "description" in changes:
        _sync_rules(session, [row])  # re-read prerequisites; admin corrections are kept
    if log:
        audit(session, actor, "course.edit", row.code, {"changes": changes})
        bump_revision(session)
    return changes


def revert_course(session: Session, row: CourseRow, actor: str) -> None:
    """Go back to the values from the course files."""
    if row.imported_values is None:
        raise EditError(f"{row.code} has no imported values to go back to; it was added in the admin page")
    restored = row.imported_values
    for name in FIELDS:
        setattr(row, name, restored.get(name))
    row.admin_edited, row.imported_values, row.source_changed = False, None, False
    session.flush()
    _sync_rules(session, [row])
    audit(session, actor, "course.revert", row.code, {"values": restored})
    bump_revision(session)


def set_course_hidden(session: Session, row: CourseRow, hidden: bool, actor: str) -> None:
    if row.hidden == hidden:
        return
    row.hidden = hidden
    audit(session, actor, "course.hide" if hidden else "course.show", row.code, {})
    bump_revision(session)


def _sync_rules(session: Session, rows: Iterable[CourseRow]) -> None:
    subjects = frozenset(code.split(" ")[0] for code in session.scalars(select(CourseRow.code)))
    courses = {row.code: Course(row.code, row.title, row.units, row.description) for row in rows}
    sync_rules(session, courses, subjects, {})


# ---------------------------------------------------------------------------
# Bulk courses (a CSV, a paste from a spreadsheet, or an .xlsx sheet)
# ---------------------------------------------------------------------------

COURSE_COLUMNS = {
    "code": ("code", "course_code", "course", "course_id", "catalog_code"),
    "title": ("title", "course_title", "name", "course_name", "long_title"),
    "units": ("units", "credits", "credit_hours", "credit", "unit"),
    "description": ("description", "course_description", "desc"),
    "component": ("component", "type", "course_component"),
    "offered_terms": ("offered_terms", "offered", "seasons", "terms", "offered_in"),
    "notices": ("notices", "notes", "notice"),
    "hidden": ("hidden", "hide"),
}
SCHEDULE_COLUMNS = {
    "code": ("code", "course_code", "course", "course_id"),
    "subject": ("subject", "subject_code", "dept", "department"),
    "number": ("catalog", "catalog_number", "catalog_nbr", "number", "course_number", "nbr"),
    "section": ("section", "sec", "class_section", "section_number"),
    "days": ("days", "day", "meeting_days", "pattern"),
    "time": ("time", "times", "meeting_time", "meeting_times", "class_time"),
    "start": ("start", "start_time", "begins"),
    "end": ("end", "end_time", "ends"),
    "instructor": ("instructor", "instructors", "teacher", "faculty", "professor"),
    "room": ("room", "location", "facility", "building_room"),
}
TRUE_WORDS = {"yes", "y", "true", "1", "hidden", "hide"}
FALSE_WORDS = {"no", "n", "false", "0", "shown", "show", "visible"}
EVERY_TERM_WORDS = {"any", "all", "every", "every term", "fall and spring", "regular"}


RowAction = Literal["create", "update", "unchanged", "error", "skip"]


@dataclass
class PlannedRow:
    line: int
    code: str | None
    action: RowAction
    messages: list[str] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)
    hidden: bool | None = None


def recognised(table: Table, columns: dict[str, tuple[str, ...]]) -> tuple[list[str], list[str]]:
    known = {alias for aliases in columns.values() for alias in aliases}
    return [c for c in table.columns if c in known], [c for c in table.columns if c not in known]


def plan_course_rows(session: Session, table: Table) -> list[PlannedRow]:
    """What each row would do. Blank cells keep a course's current value."""
    if not any(column in COURSE_COLUMNS["code"] for column in table.columns):
        raise EditError("The table needs a course code column (for example 'code')")
    wanted = {code for row in table.rows if (code := normalize_code(row.pick(*COURSE_COLUMNS["code"])))}
    existing = {row.code: row for row in session.scalars(select(CourseRow).where(CourseRow.code.in_(wanted)))}
    seen: set[str] = set()
    planned = []
    for row in table.rows:
        raw_code = row.pick(*COURSE_COLUMNS["code"])
        code = normalize_code(raw_code)
        result = PlannedRow(row.line, code or raw_code or None, "error")
        planned.append(result)
        if code is None:
            result.messages.append(
                f"{raw_code!r} is not a course code like 'CSC 231'" if raw_code else "No code"
            )
            continue
        if code in seen:
            result.messages.append(f"{code} appears more than once; only the first row is used")
            continue
        seen.add(code)
        current = existing.get(code)
        values, problems = _course_cells(row, row_values(current) if current else None)
        hidden_text = row.pick(*COURSE_COLUMNS["hidden"]).lower()
        if hidden_text:
            if hidden_text in TRUE_WORDS | FALSE_WORDS:
                result.hidden = hidden_text in TRUE_WORDS
            else:
                problems.append(f"Hidden must be yes or no, not {hidden_text!r}")
        if current is None and not values.get("title"):
            problems.append("A new course needs a title")
        if problems:
            result.messages.extend(problems)
            continue
        result.values = values
        if current is None:
            result.action = "create"
        elif row_values(current) != values or (result.hidden is not None and result.hidden != current.hidden):
            result.action = "update"
            result.messages = [
                f"{FIELD_NAMES.get(name, name)}: {_short(getattr(current, name), name)} → "
                f"{_short(values[name], name)}"
                for name in FIELDS
                if getattr(current, name) != values[name]
            ]
            if result.hidden is not None and result.hidden != current.hidden:
                result.messages.append("hidden" if result.hidden else "shown again")
        else:
            result.action = "unchanged"
    return planned


def apply_course_rows(session: Session, rows: list[PlannedRow], actor: str) -> dict[str, int]:
    if any(row.action == "error" for row in rows):
        raise EditError("Fix the rows with problems first; nothing was saved")
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    for planned in rows:
        assert planned.code is not None
        if planned.action == "create":
            create_course(
                session, planned.code, planned.values, actor, hidden=bool(planned.hidden), log=False
            )
            counts["created"] += 1
        elif planned.action == "update":
            row = session.get(CourseRow, planned.code)
            assert row is not None
            update_course(session, row, planned.values, actor, log=False)
            if planned.hidden is not None:
                row.hidden = planned.hidden
            counts["updated"] += 1
        else:
            counts["unchanged"] += 1
    if counts["created"] or counts["updated"]:
        audit(
            session,
            actor,
            "course.bulk",
            f"{counts['created']} created, {counts['updated']} updated",
            {
                "created": [r.code for r in rows if r.action == "create"],
                "updated": [r.code for r in rows if r.action == "update"],
            },
        )
        bump_revision(session)
    return counts


def _course_cells(row: TableRow, current: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    base: dict[str, Any] = (
        dict(current)
        if current
        else {
            "title": "",
            "units": None,
            "description": "",
            "component": None,
            "notices": [],
            "offered_terms": None,
        }
    )
    problems = []
    title = row.pick(*COURSE_COLUMNS["title"])
    if title:
        base["title"] = title[:300]
    units = row.pick(*COURSE_COLUMNS["units"])
    if units:
        try:
            number = float(units)
        except ValueError:
            problems.append(f"Credits must be a number, not {units!r}")
        else:
            if 0 <= number <= 30:
                base["units"] = number
            else:
                problems.append("Credits must be between 0 and 30")
    description = row.pick(*COURSE_COLUMNS["description"])
    if description:
        base["description"] = description
    component = row.pick(*COURSE_COLUMNS["component"])
    if component:
        base["component"] = component[:60]
    offered = row.pick(*COURSE_COLUMNS["offered_terms"])
    if offered:
        seasons, problem = parse_seasons(offered)
        if problem:
            problems.append(problem)
        else:
            base["offered_terms"] = seasons
    notices = row.pick(*COURSE_COLUMNS["notices"])
    if notices:
        base["notices"] = [
            part.strip()[:300] for part in notices.replace("\n", "|").split("|") if part.strip()
        ][:20]
    return base, problems


def parse_seasons(text: str) -> tuple[list[str] | None, str | None]:
    """'Fall; Spring' -> ['fall', 'spring']; 'any' -> None (every regular term)."""
    lower = text.strip().lower()
    if lower in EVERY_TERM_WORDS:
        return None, None
    words = lower.replace(";", ",").replace("/", ",").replace(" and ", ",").split(",")
    seasons = set()
    for word in (w.strip().removesuffix(" only") for w in words):
        if not word:
            continue
        if word not in OFFERED_TERM_NAMES:
            return None, f"Offered terms must be fall, spring or summer, not {word!r}"
        seasons.add(word)
    return sorted(seasons) or None, None


def _short(value: Any, name: str) -> str:
    """A field's value as an admin reads it in the upload preview."""
    if value is None:
        text = "every term" if name == "offered_terms" else "none"
    elif isinstance(value, float) and value.is_integer():
        text = str(int(value))
    elif isinstance(value, list):
        text = ", ".join(str(item) for item in value) or "none"
    else:
        text = str(value)
    return text if len(text) <= 60 else f"{text[:57]}…"


# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------


def check_program(session: Session, program: Program) -> ValidationReport:
    report = ValidationReport(program.id)
    validate_program(program, load_catalog(session, current_revision(session)), report, ADMIN_FORM)
    return report


def save_program(
    session: Session,
    program: Program,
    *,
    actor: str,
    creating: bool,
    published: bool,
    accept_warnings: bool,
) -> ValidationReport:
    """Validate and store ``program``. Errors block saving; publishing with warnings needs consent."""
    existing = session.get(ProgramRow, program.id)
    if creating and existing is not None:
        raise EditError(f"A program with the id {program.id!r} already exists; choose another id")
    if not creating and existing is None:
        raise EditError(f"There is no program {program.id!r}")
    report = check_program(session, program)
    if not report.ok:
        return report
    if published and report.warnings and not accept_warnings:
        raise EditError("Check the warnings, then confirm to publish with them")
    origin = existing.origin if existing is not None else ADMIN_SOURCE
    hidden = existing.hidden if existing is not None else False
    sis_title = existing.sis_title if existing is not None else None
    groups = write_program(
        session,
        program,
        published=published,
        sis_title=sis_title,
        origin=origin,
        admin_edited=True,
        hidden=hidden,
    )
    audit(
        session,
        actor,
        "program.create" if creating else "program.edit",
        program.id,
        {"name": program.name, "kind": program.kind, "groups": groups, "published": published},
    )
    bump_revision(session)
    return report


def set_program_hidden(session: Session, row: ProgramRow, hidden: bool, actor: str) -> None:
    if row.hidden == hidden:
        return
    row.hidden = hidden
    audit(session, actor, "program.hide" if hidden else "program.show", row.id, {"name": row.name})
    bump_revision(session)


# ---------------------------------------------------------------------------
# Term schedules (F0.5)
# ---------------------------------------------------------------------------


@dataclass
class Offering:
    code: str
    section: str = ""
    days: str = ""
    time: str = ""
    instructor: str = ""
    room: str = ""


def plan_schedule_rows(session: Session, table: Table) -> tuple[list[Offering], list[PlannedRow]]:
    """The sections to store, and the rows that were skipped (with the reason)."""
    columns = table.columns
    has_code = any(c in SCHEDULE_COLUMNS["code"] for c in columns)
    has_parts = any(c in SCHEDULE_COLUMNS["subject"] for c in columns) and any(
        c in SCHEDULE_COLUMNS["number"] for c in columns
    )
    if not has_code and not has_parts:
        raise EditError("The table needs a course code column, or subject and catalog number columns")
    known = set(session.scalars(select(CourseRow.code)))
    offerings: list[Offering] = []
    skipped: list[PlannedRow] = []
    seen: set[tuple[str, str]] = set()
    for row in table.rows:
        raw = row.pick(*SCHEDULE_COLUMNS["code"]) or " ".join(
            part
            for part in (row.pick(*SCHEDULE_COLUMNS["subject"]), row.pick(*SCHEDULE_COLUMNS["number"]))
            if part
        )
        code = normalize_code(raw)
        if code is None:
            skipped.append(
                PlannedRow(
                    row.line,
                    raw or None,
                    "skip",
                    [f"{raw!r} is not a course code" if raw else "No course code"],
                )
            )
            continue
        if code not in known:
            skipped.append(
                PlannedRow(
                    row.line, code, "skip", ["Not in the course catalog; add the course first to include it"]
                )
            )
            continue
        section = row.pick(*SCHEDULE_COLUMNS["section"])[:20]
        if (code, section) in seen:
            skipped.append(
                PlannedRow(row.line, code, "skip", [f"Section {section or '(none)'} appears twice"])
            )
            continue
        seen.add((code, section))
        start, end = row.pick(*SCHEDULE_COLUMNS["start"]), row.pick(*SCHEDULE_COLUMNS["end"])
        time = row.pick(*SCHEDULE_COLUMNS["time"]) or (f"{start}–{end}" if start and end else start or end)
        offerings.append(
            Offering(
                code=code,
                section=section,
                days=row.pick(*SCHEDULE_COLUMNS["days"])[:40],
                time=time[:40],
                instructor=row.pick(*SCHEDULE_COLUMNS["instructor"])[:120],
                room=row.pick(*SCHEDULE_COLUMNS["room"])[:60],
            )
        )
    return offerings, skipped


def replace_schedule(session: Session, term: Term, offerings: list[Offering], actor: str) -> TermScheduleRow:
    """The term's schedule becomes exactly ``offerings``."""
    if not offerings:
        raise EditError("No sections to save: every row was skipped")
    season = term.season.name.lower()
    old = session.scalar(
        select(TermScheduleRow).where(TermScheduleRow.year == term.year, TermScheduleRow.season == season)
    )
    if old is not None:
        session.delete(old)  # its sections go with it
        session.flush()
    schedule = TermScheduleRow(year=term.year, season=season, updated_by=actor)
    schedule.offerings = [
        TermOfferingRow(
            course_code=offering.code,
            section=offering.section,
            days=offering.days,
            time=offering.time,
            instructor=offering.instructor,
            room=offering.room,
            position=index,
        )
        for index, offering in enumerate(offerings)
    ]
    session.add(schedule)
    session.flush()
    audit(
        session,
        actor,
        "schedule.upload",
        term.label,
        {"sections": len(offerings), "courses": len({o.code for o in offerings})},
    )
    bump_revision(session)
    return schedule


def delete_schedule(session: Session, schedule: TermScheduleRow, actor: str) -> None:
    label = schedule_term(schedule).label
    session.delete(schedule)
    session.flush()
    audit(session, actor, "schedule.delete", label, {})
    bump_revision(session)


def schedule_term(schedule: TermScheduleRow) -> Term:
    return Term(schedule.year, OFFERED_TERM_NAMES[schedule.season])


def course_offerings(
    session: Session, code: str, *, since: Term | None = None
) -> list[tuple[Term, list[TermOfferingRow]]]:
    """A course's sections on published schedules, by term (from ``since`` onward)."""
    by_term: dict[Term, list[TermOfferingRow]] = {}
    rows = session.execute(
        select(TermOfferingRow, TermScheduleRow)
        .join(TermScheduleRow)
        .where(TermOfferingRow.course_code == code)
        .order_by(TermOfferingRow.position)
    )
    for offering, schedule in rows:
        term = schedule_term(schedule)
        if since is None or term >= since:
            by_term.setdefault(term, []).append(offering)
    return sorted(by_term.items())
