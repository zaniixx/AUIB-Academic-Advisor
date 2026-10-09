"""Admin endpoints for editing the catalog: courses, bulk uploads, programs, term schedules, backups.

Requisite rules are reviewed and corrected through ``admin.py``; this module adds what an
admin needs beyond the imported files. Every change is audited and raises the catalog
revision (see ``app.services.catalog_edit``).
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from sqlalchemy import func, select

from app.api import admin_schemas as a
from app.api import convert
from app.api import schemas as s
from app.api.deps import AdminDep, CatalogDep, SessionDep, TodayDep
from app.api.routes.admin import rule_out
from app.domain.catalog import Catalog, Group, Program
from app.domain.codes import normalize_code
from app.domain.requisites import RuleSyntaxError, format_rule, parse_rule, to_json
from app.domain.terms import Season, Term, current_term
from app.importer.load import bump_revision
from app.importer.package import unique_key
from app.importer.tables import Table, TableError, read_text, read_xlsx
from app.importer.validate import Finding, ValidationReport
from app.models import CourseRow, ProgramRow, RequirementGroupRow, RequisiteRuleRow, TermScheduleRow
from app.services import catalog_edit as edit
from app.services.backup import (
    BackupError,
    make_backup,
    read_backup,
    restore_data,
    row_counts,
    schema_problem,
)
from app.services.catalog_cache import current_revision, load_catalog

router = APIRouter(prefix="/api/v1/admin", tags=["admin: catalog"])

CourseFilter = Literal["all", "hidden", "edited", "admin", "source_changed"]


def _bad_request(error: Exception) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error))


def _conflict(error: Exception) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(error))


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


def _course_row(session: SessionDep, code: str) -> CourseRow:
    normal = normalize_code(code)
    row = session.get(CourseRow, normal) if normal else None
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No course {code!r} in the catalog")
    return row


def _course_summary(row: CourseRow) -> a.AdminCourseSummaryOut:
    return a.AdminCourseSummaryOut(
        code=row.code,
        title=row.title,
        units=row.units,
        hidden=row.hidden,
        admin_edited=row.admin_edited,
        source_changed=row.source_changed,
        origin="admin" if row.source_program == edit.ADMIN_SOURCE else "import",
    )


def _course_out(session: SessionDep, row: CourseRow, catalog: Catalog, today: TodayDep) -> a.AdminCourseOut:
    rules = session.scalars(
        select(RequisiteRuleRow)
        .where(RequisiteRuleRow.course_code == row.code)
        .order_by(RequisiteRuleRow.kind)
    )
    counts_toward = [
        f"{program.name}: {group.label}"
        for program in sorted(catalog.programs.values(), key=lambda p: p.name)
        for group in program.leaf_groups()
        if row.code in group.courses and not group.is_open_pool
    ]
    return a.AdminCourseOut(
        **_course_summary(row).model_dump(),
        description=row.description,
        component=row.component,
        notices=list(row.notices or []),
        offered_terms=row.offered_terms,
        imported_values=row.imported_values,
        rules=[rule_out(rule, row.title) for rule in rules],
        counts_toward=counts_toward,
        offerings=convert.term_offerings_out(
            edit.course_offerings(session, row.code, since=current_term(today)), catalog
        ),
    )


@router.get("/courses", summary="Every course, including hidden ones and ones added here")
def list_courses(
    session: SessionDep,
    _admin: AdminDep,
    show: CourseFilter = "all",
    q: Annotated[str | None, Query(max_length=60)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> a.AdminCourseListOut:
    filters = {
        "hidden": CourseRow.hidden,
        "edited": CourseRow.admin_edited & (CourseRow.source_program != edit.ADMIN_SOURCE),
        "admin": CourseRow.source_program == edit.ADMIN_SOURCE,
        "source_changed": CourseRow.source_changed,
    }
    query = select(CourseRow)
    if show in filters:
        query = query.where(filters[show])
    if q:
        needle = f"%{q.strip().upper()}%"
        query = query.where(
            func.upper(CourseRow.code).like(needle) | func.upper(CourseRow.title).like(needle)
        )
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(query.order_by(CourseRow.code).limit(limit).offset(offset))
    counts = {
        name: session.scalar(select(func.count()).select_from(CourseRow).where(condition)) or 0
        for name, condition in filters.items()
    }
    counts["all"] = session.scalar(select(func.count()).select_from(CourseRow)) or 0
    return a.AdminCourseListOut(total=total, counts=counts, courses=[_course_summary(row) for row in rows])


@router.get(
    "/courses/{code}", summary="A course with its rules, the requirements it counts toward and its sections"
)
def course_detail(
    code: str, session: SessionDep, catalog: CatalogDep, today: TodayDep, _admin: AdminDep
) -> a.AdminCourseOut:
    return _course_out(session, _course_row(session, code), catalog, today)


@router.post("/courses", status_code=status.HTTP_201_CREATED, summary="Add a course by hand")
def create_course(
    body: a.CourseCreateIn, session: SessionDep, catalog: CatalogDep, today: TodayDep, actor: AdminDep
) -> a.AdminCourseOut:
    values = body.model_dump(exclude={"code", "hidden"})
    try:
        row = edit.create_course(session, body.code, values, actor, hidden=body.hidden)
    except edit.EditError as error:
        raise _conflict(error) from error
    return _course_out(session, row, catalog, today)


@router.put("/courses/{code}", summary="Edit a course; later imports keep the edit")
def update_course(
    code: str,
    body: a.CourseFieldsIn,
    session: SessionDep,
    catalog: CatalogDep,
    today: TodayDep,
    actor: AdminDep,
) -> a.AdminCourseOut:
    row = _course_row(session, code)
    edit.update_course(session, row, body.model_dump(), actor)
    return _course_out(session, row, catalog, today)


@router.post(
    "/courses/{code}/revert", summary="Drop the admin's edit and use the values from the course files"
)
def revert_course(
    code: str, session: SessionDep, catalog: CatalogDep, today: TodayDep, actor: AdminDep
) -> a.AdminCourseOut:
    row = _course_row(session, code)
    try:
        edit.revert_course(session, row, actor)
    except edit.EditError as error:
        raise _conflict(error) from error
    return _course_out(session, row, catalog, today)


@router.put("/courses/{code}/hidden", summary="Hide a course from students and plans, or show it again")
def hide_course(code: str, body: a.HiddenIn, session: SessionDep, actor: AdminDep) -> a.AdminCourseSummaryOut:
    row = _course_row(session, code)
    edit.set_course_hidden(session, row, body.hidden, actor)
    return _course_summary(row)


@router.post(
    "/courses/{code}/rules",
    status_code=status.HTTP_201_CREATED,
    summary="Add a prerequisite or corequisite rule that the description does not state",
)
def add_rule(code: str, body: a.RuleCreateIn, session: SessionDep, actor: AdminDep) -> s.AdminRuleOut:
    row = _course_row(session, code)
    if session.scalar(
        select(RequisiteRuleRow).where(
            RequisiteRuleRow.course_code == row.code, RequisiteRuleRow.kind == body.kind
        )
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{row.code} already has a {body.kind} rule; correct it instead"
        )
    try:
        expr = parse_rule(body.rule)
    except RuleSyntaxError as error:
        raise _bad_request(error) from error
    if expr is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Write the rule; NONE needs no rule at all"
        )
    now = datetime.now(UTC)
    rule = RequisiteRuleRow(
        course_code=row.code,
        kind=body.kind,
        source_text="",  # added by an admin: there is no SIS sentence
        parsed_expr=None,
        parse_status="parsed",
        unparsed_text="",
        override_expr=to_json(expr),
        override_note=body.note,
        reviewed=True,
        reviewed_by=actor,
        reviewed_at=now,
    )
    session.add(rule)
    session.flush()
    edit.audit(
        session, actor, "rule.add", f"{row.code} {body.kind}", {"rule": format_rule(expr), "note": body.note}
    )
    bump_revision(session)
    return rule_out(rule, row.title)


@router.delete(
    "/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a rule an admin added"
)
def delete_rule(rule_id: int, session: SessionDep, actor: AdminDep) -> Response:
    rule = session.get(RequisiteRuleRow, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No rule {rule_id}")
    if rule.source_text:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This rule comes from the SIS description; correct it to NONE instead of deleting it",
        )
    edit.audit(session, actor, "rule.delete", f"{rule.course_code} {rule.kind}", {})
    session.delete(rule)
    bump_revision(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _table(body: a.TableIn) -> Table:
    try:
        data = body.xlsx_bytes()
        return read_xlsx(data) if data is not None else read_text(body.text or "")
    except (TableError, ValueError) as error:
        raise _bad_request(error) from error


def _row_out(row: edit.PlannedRow) -> a.RowOut:
    return a.RowOut(line=row.line, code=row.code, action=row.action, messages=row.messages)


@router.post(
    "/courses/bulk",
    summary="Add or update many courses from a CSV, a spreadsheet paste or an .xlsx sheet",
    description="With dry_run (the default) nothing is saved: the answer previews every row. "
    "Saving is all or nothing, and only when no row has a problem. Blank cells keep the current value.",
)
def bulk_courses(body: a.TableIn, session: SessionDep, actor: AdminDep) -> a.CourseBulkOut:
    table = _table(body)
    try:
        planned = edit.plan_course_rows(session, table)
    except edit.EditError as error:
        raise _bad_request(error) from error
    columns, ignored = edit.recognised(table, edit.COURSE_COLUMNS)
    counts: dict[str, int] = {}
    for row in planned:
        counts[row.action] = counts.get(row.action, 0) + 1
    applied = False
    if not body.dry_run:
        try:
            edit.apply_course_rows(session, planned, actor)
        except edit.EditError as error:
            raise _bad_request(error) from error
        applied = True
    return a.CourseBulkOut(
        applied=applied,
        counts=counts,
        columns=columns,
        ignored_columns=ignored,
        rows=[_row_out(row) for row in planned if row.action != "unchanged"],
    )


# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------


def _program_from_draft(draft: a.ProgramDraftIn) -> Program:
    used: set[str] = set()

    def convert_group(group: a.GroupDraftIn) -> Group:
        title = group.title or group.label
        return Group(
            key=unique_key(title, used),
            title=title,
            label=group.label,
            units_required=group.units_required,
            role=group.role,
            courses=tuple(group.courses),
            children=tuple(convert_group(child) for child in group.children),
        )

    return Program(
        id=draft.id,
        name=draft.name,
        kind=draft.kind,
        total_units=draft.total_units,
        root=convert_group(draft.root),
        catalog_year=draft.catalog_year,
        source=draft.source,
        source_date=draft.source_date.isoformat() if draft.source_date else None,
        published=draft.published,
        family=draft.family if draft.family and draft.family != draft.id else "",
        valid_from=Term.parse(draft.valid_from) if draft.valid_from else None,
        standard_terms=draft.standard_terms,
    )


def _findings(report: ValidationReport) -> list[a.FindingOut]:
    def out(finding: Finding) -> a.FindingOut:
        return a.FindingOut(severity=finding.severity.value, where=finding.where, message=finding.message)

    return [out(f) for f in report.findings]


def _group_out(group: Group) -> a.GroupDraftOut:
    return a.GroupDraftOut(
        key=group.key,
        label=group.label,
        title=group.title,
        role=group.role,
        units_required=group.units_required,
        courses=list(group.courses),
        children=[_group_out(child) for child in group.children],
    )


def _program_summary(row: ProgramRow, groups: int) -> a.AdminProgramSummaryOut:
    return a.AdminProgramSummaryOut(
        id=row.id,
        name=row.name,
        kind=row.kind,
        catalog_year=row.catalog_year,
        total_units=row.total_units,
        published=row.published,
        hidden=row.hidden,
        origin="admin" if row.origin == edit.ADMIN_SOURCE else "import",
        admin_edited=row.admin_edited,
        groups=groups,
        family=row.family or row.id,
        valid_from=row.valid_from,
        standard_terms=row.standard_terms or 8,
    )


def _program_row(session: SessionDep, program_id: str) -> ProgramRow:
    row = session.get(ProgramRow, program_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No program {program_id!r}")
    return row


def _program_out(session: SessionDep, program_id: str) -> a.AdminProgramOut:
    # Read straight from the database, so an edit made in this request shows at once.
    program = load_catalog(session, current_revision(session)).programs.get(program_id)
    row = _program_row(session, program_id)
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Program {program_id!r} has no requirements")
    return a.AdminProgramOut(
        **_program_summary(row, len(program.groups())).model_dump(),
        source=row.source,
        source_date=row.source_date,
        root=_group_out(program.root),
    )


@router.get("/programs", summary="Every major and minor, including hidden and unpublished ones")
def list_programs(session: SessionDep, _admin: AdminDep) -> list[a.AdminProgramSummaryOut]:
    counted = select(RequirementGroupRow.program_id, func.count()).group_by(RequirementGroupRow.program_id)
    groups: dict[str, int] = dict(session.execute(counted).tuples().all())
    rows = session.scalars(select(ProgramRow).order_by(ProgramRow.kind, ProgramRow.name))
    listed = [_program_summary(row, groups.get(row.id, 0)) for row in rows]
    # Versions of one program sit together, oldest first.
    first_term = {out.id: Term.parse(out.valid_from) if out.valid_from else None for out in listed}
    return sorted(
        listed,
        key=lambda out: (
            out.kind,
            out.family,
            first_term[out.id] is not None,
            first_term[out.id] or Term(1, Season.SPRING),
        ),
    )


@router.get("/programs/{program_id}", summary="A program's requirement tree, ready to edit")
def program_detail(program_id: str, session: SessionDep, _admin: AdminDep) -> a.AdminProgramOut:
    return _program_out(session, program_id)


@router.post("/programs/check", summary="Check a draft program without saving it")
def check_program(body: a.ProgramDraftIn, session: SessionDep, _admin: AdminDep) -> a.ProgramCheckOut:
    report = edit.check_program(session, _program_from_draft(body))
    return a.ProgramCheckOut(ok=report.ok, findings=_findings(report), stats=report.stats)


def _save(body: a.ProgramDraftIn, session: SessionDep, actor: str, *, creating: bool) -> a.ProgramSaveOut:
    try:
        report = edit.save_program(
            session,
            _program_from_draft(body),
            actor=actor,
            creating=creating,
            published=body.published,
            accept_warnings=body.accept_warnings,
        )
    except edit.EditError as error:
        raise _conflict(error) from error
    if not report.ok:
        return a.ProgramSaveOut(saved=False, program=None, findings=_findings(report))
    return a.ProgramSaveOut(saved=True, program=_program_out(session, body.id), findings=_findings(report))


@router.post("/programs", summary="Add a major or minor by hand")
def create_program(body: a.ProgramDraftIn, session: SessionDep, actor: AdminDep) -> a.ProgramSaveOut:
    return _save(body, session, actor, creating=True)


@router.put("/programs/{program_id}", summary="Replace a program's details and requirement tree")
def update_program(
    program_id: str, body: a.ProgramDraftIn, session: SessionDep, actor: AdminDep
) -> a.ProgramSaveOut:
    if body.id != program_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A program's id cannot be changed")
    return _save(body, session, actor, creating=False)


@router.put("/programs/{program_id}/hidden", summary="Hide a major or minor from students, or show it again")
def hide_program(
    program_id: str, body: a.HiddenIn, session: SessionDep, actor: AdminDep
) -> a.AdminProgramSummaryOut:
    row = _program_row(session, program_id)
    edit.set_program_hidden(session, row, body.hidden, actor)
    groups = session.scalar(
        select(func.count()).select_from(RequirementGroupRow).where(RequirementGroupRow.program_id == row.id)
    )
    return _program_summary(row, groups or 0)


# ---------------------------------------------------------------------------
# Term schedules (F0.5)
# ---------------------------------------------------------------------------


def _schedule_summary(row: TermScheduleRow) -> a.ScheduleSummaryOut:
    return a.ScheduleSummaryOut(
        term=convert.required_term(edit.schedule_term(row)),
        courses=len({offering.course_code for offering in row.offerings}),
        sections=len(row.offerings),
        updated_at=row.updated_at,
        updated_by=row.updated_by,
    )


def _schedule_row(session: SessionDep, year: int, season: str) -> TermScheduleRow:
    row = session.scalar(
        select(TermScheduleRow).where(TermScheduleRow.year == year, TermScheduleRow.season == season.lower())
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No schedule for {season.capitalize()} {year}")
    return row


@router.get("/schedules", summary="Published term schedules, newest first")
def list_schedules(session: SessionDep, _admin: AdminDep) -> list[a.ScheduleSummaryOut]:
    rows = session.scalars(select(TermScheduleRow))
    return sorted(
        (_schedule_summary(row) for row in rows),
        key=lambda out: (out.term.year, out.term.season),
        reverse=True,
    )


@router.get("/schedules/{year}/{season}", summary="A term's schedule, section by section")
def schedule_detail(
    year: Annotated[int, Path(ge=2000, le=2100)],
    season: Literal["spring", "summer", "fall"],
    session: SessionDep,
    catalog: CatalogDep,
    _admin: AdminDep,
) -> a.ScheduleOut:
    row = _schedule_row(session, year, season)
    return a.ScheduleOut(
        **_schedule_summary(row).model_dump(),
        offerings=[convert.offering_out(offering, catalog) for offering in row.offerings],
    )


@router.post(
    "/schedules",
    summary="Publish a term's course schedule from a CSV, a spreadsheet paste or an .xlsx sheet",
    description="The term's schedule is replaced by the uploaded one. Rows for courses that are not in the "
    "catalog are skipped and listed. With dry_run (the default) nothing is saved.",
)
def upload_schedule(body: a.ScheduleUploadIn, session: SessionDep, actor: AdminDep) -> a.ScheduleUploadOut:
    term = Term.parse(body.term)
    assert term is not None  # checked by the schema
    table = _table(body)
    try:
        offerings, skipped = edit.plan_schedule_rows(session, table)
    except edit.EditError as error:
        raise _bad_request(error) from error
    columns, ignored = edit.recognised(table, edit.SCHEDULE_COLUMNS)
    applied = False
    if not body.dry_run:
        try:
            edit.replace_schedule(session, term, offerings, actor)
        except edit.EditError as error:
            raise _bad_request(error) from error
        applied = True
    return a.ScheduleUploadOut(
        applied=applied,
        term=convert.required_term(term),
        counts={
            "sections": len(offerings),
            "courses": len({offering.code for offering in offerings}),
            "skipped": len(skipped),
        },
        columns=columns,
        ignored_columns=ignored,
        rows=[_row_out(row) for row in skipped],
    )


@router.delete(
    "/schedules/{year}/{season}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a term's schedule; that term is planned by season again",
)
def delete_schedule(
    year: int, season: Literal["spring", "summer", "fall"], session: SessionDep, actor: AdminDep
) -> Response:
    edit.delete_schedule(session, _schedule_row(session, year, season), actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------


@router.post(
    "/backup",
    summary="Download an encrypted backup of the whole database",
    description="AES-256-GCM, with the key derived from the passphrase (scrypt). The passphrase is not "
    "stored anywhere: without it the backup cannot be read or restored.",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}, "description": "The encrypted backup"}},
)
def backup(body: a.BackupIn, session: SessionDep, actor: AdminDep) -> Response:
    try:
        blob, counts = make_backup(session, body.passphrase)
    except BackupError as error:
        raise _bad_request(error) from error
    edit.audit(session, actor, "backup.export", "database", {"rows": counts, "bytes": len(blob)})
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    return Response(
        content=blob,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="auib-advisor-backup-{stamp}.aab"'},
    )


def _read_upload(body: a.RestoreFileIn) -> dict[str, Any]:
    try:
        return read_backup(body.backup_bytes(), body.passphrase)
    except (BackupError, ValueError) as error:
        raise _bad_request(error) from error


@router.post(
    "/restore/check",
    summary="Open an uploaded backup and compare it with the data now, without changing anything",
)
def check_restore(body: a.RestoreFileIn, session: SessionDep, _admin: AdminDep) -> a.BackupCheckOut:
    data = _read_upload(body)
    now = row_counts(session)
    problem = schema_problem(session, data)
    return a.BackupCheckOut(
        created_at=str(data.get("created_at", "")),
        app_version=str(data.get("app_version", "")),
        schema_revision=data.get("schema_revision"),
        restorable=problem is None,
        problem=problem,
        tables=[
            a.BackupTableOut(name=name, in_backup=len(data["tables"].get(name, [])), now=count)
            for name, count in now.items()
        ],
    )


@router.post(
    "/restore",
    summary="Restore the data from an uploaded backup",
    description="Replaces courses, rules, programs, term schedules and import history with the backup's, in "
    "one transaction. The audit log is kept and records the restore. The data from just before the restore "
    "is returned as an encrypted backup (same passphrase), so the restore can be undone.",
)
def restore(body: a.RestoreIn, session: SessionDep, actor: AdminDep) -> a.RestoreOut:
    data = _read_upload(body)
    problem = schema_problem(session, data)
    if problem:
        raise HTTPException(status.HTTP_409_CONFLICT, problem)
    try:
        previous, _counts = make_backup(session, body.passphrase)
    except BackupError as error:
        raise _bad_request(error) from error
    restored = restore_data(session, data, keep_audit_log=True)
    edit.audit(
        session,
        actor,
        "backup.restore",
        "database",
        {"made": data.get("created_at"), "rows": restored, "previous_returned": True},
    )
    session.commit()  # the change is saved before the answer says so
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    return a.RestoreOut(
        restored=restored,
        audit_log_kept=True,
        previous=a.BackupFileOut(
            filename=f"auib-advisor-before-restore-{stamp}.aab",
            data_base64=base64.b64encode(previous).decode("ascii"),
        ),
    )
