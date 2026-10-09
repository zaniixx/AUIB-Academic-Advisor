"""Admin endpoints: review and correct requisite rules (F0.2, F0.3), import history and audit log (F9.3).

Every change is written to the audit log and bumps the catalog revision so all
API workers pick it up on their next request.
"""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api import schemas as s
from app.api.deps import AdminDep, CatalogDep, SessionDep
from app.domain.requisites import (
    RuleSyntaxError,
    course_codes,
    describe,
    format_rule,
    from_json,
    parse_rule,
    to_json,
)
from app.importer.load import bump_revision
from app.models import AuditLogRow, CourseRow, ImportRunRow, RequisiteRuleRow

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

RuleFilter = Literal["all", "needs_review", "partial", "unparsed", "overridden", "source_changed", "reviewed"]


def rule_out(row: RequisiteRuleRow, title: str) -> s.AdminRuleOut:
    parsed = from_json(row.parsed_expr)
    effective = from_json(row.effective_expr)
    override = None
    if row.override_is_none:
        override = "NONE"
    elif row.override_expr is not None:
        override = format_rule(from_json(row.override_expr))
    return s.AdminRuleOut(
        id=row.id,
        course_code=row.course_code,
        course_title=title,
        kind=row.kind,
        source_text=row.source_text,
        status=row.parse_status,
        unparsed_text=row.unparsed_text,
        parsed_rule=format_rule(parsed),
        parsed_english=describe(parsed),
        override_rule=override,
        override_note=row.override_note,
        effective_rule=format_rule(effective),
        effective_english=describe(effective),
        reviewed=row.reviewed,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        source_changed=row.source_changed,
    )


def _audit(session: SessionDep, actor: str, action: str, target: str, detail: dict[str, object]) -> None:
    session.add(AuditLogRow(actor=actor, action=action, target=target, detail=detail))


def _get_rule(session: SessionDep, rule_id: int) -> RequisiteRuleRow:
    row = session.get(RequisiteRuleRow, rule_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No rule {rule_id}")
    return row


@router.get("/rules", summary="Rules to review, each beside its source sentence")
def list_rules(
    session: SessionDep,
    _admin: AdminDep,
    show: RuleFilter = "needs_review",
    q: Annotated[str | None, Query(max_length=60)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> s.AdminRuleListOut:
    query = select(RequisiteRuleRow, CourseRow.title).join(CourseRow)
    filters = {
        "needs_review": ~RequisiteRuleRow.reviewed | RequisiteRuleRow.source_changed,
        "partial": RequisiteRuleRow.parse_status == "partial",
        "unparsed": RequisiteRuleRow.parse_status == "unparsed",
        "overridden": RequisiteRuleRow.override_expr.is_not(None) | RequisiteRuleRow.override_is_none,
        "source_changed": RequisiteRuleRow.source_changed,
        "reviewed": RequisiteRuleRow.reviewed,
    }
    if show in filters:
        query = query.where(filters[show])
    if q:
        needle = f"%{q.strip().upper()}%"
        query = query.where(
            func.upper(RequisiteRuleRow.course_code).like(needle) | func.upper(CourseRow.title).like(needle)
        )
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.execute(
        query.order_by(RequisiteRuleRow.course_code, RequisiteRuleRow.kind).limit(limit).offset(offset)
    )
    counts = {
        name: session.scalar(select(func.count()).select_from(RequisiteRuleRow).where(condition)) or 0
        for name, condition in filters.items()
    }
    counts["all"] = session.scalar(select(func.count()).select_from(RequisiteRuleRow)) or 0
    return s.AdminRuleListOut(total=total, counts=counts, rules=[rule_out(row, title) for row, title in rows])


@router.post("/rules/check", summary="Check a rule written in the rule language without saving it")
def check_rule(body: s.RuleCheckIn, catalog: CatalogDep, _admin: AdminDep) -> s.RuleCheckOut:
    try:
        expr = parse_rule(body.rule)
    except RuleSyntaxError as error:
        return s.RuleCheckOut(valid=False, error=str(error), position=error.position)
    unknown = sorted(code for code in course_codes(expr) if code not in catalog.courses)
    return s.RuleCheckOut(valid=True, rule=format_rule(expr), english=describe(expr), unknown_courses=unknown)


@router.put("/rules/{rule_id}", summary="Correct a rule by hand (F0.3); the correction survives re-imports")
def correct_rule(rule_id: int, body: s.RuleUpdateIn, session: SessionDep, actor: AdminDep) -> s.AdminRuleOut:
    row = _get_rule(session, rule_id)
    try:
        expr = parse_rule(body.rule)
    except RuleSyntaxError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    before = format_rule(from_json(row.effective_expr))
    row.override_expr = to_json(expr)
    row.override_is_none = expr is None
    row.override_note = body.note
    row.reviewed, row.reviewed_by, row.reviewed_at = True, actor, datetime.now(UTC)
    row.source_changed = False
    _audit(
        session,
        actor,
        "rule.correct",
        f"{row.course_code} {row.kind}",
        {"before": before, "after": format_rule(expr), "note": body.note},
    )
    bump_revision(session)
    title = session.get(CourseRow, row.course_code)
    return rule_out(row, title.title if title else row.course_code)


@router.post("/rules/{rule_id}/approve", summary="Mark the rule in force as checked")
def approve_rule(rule_id: int, session: SessionDep, actor: AdminDep) -> s.AdminRuleOut:
    row = _get_rule(session, rule_id)
    row.reviewed, row.reviewed_by, row.reviewed_at = True, actor, datetime.now(UTC)
    row.source_changed = False
    _audit(
        session,
        actor,
        "rule.approve",
        f"{row.course_code} {row.kind}",
        {"rule": format_rule(from_json(row.effective_expr))},
    )
    bump_revision(session)
    title = session.get(CourseRow, row.course_code)
    return rule_out(row, title.title if title else row.course_code)


@router.delete("/rules/{rule_id}/override", summary="Drop a correction and go back to the parsed rule")
def remove_override(rule_id: int, session: SessionDep, actor: AdminDep) -> s.AdminRuleOut:
    row = _get_rule(session, rule_id)
    if not row.overridden:
        raise HTTPException(status.HTTP_409_CONFLICT, "This rule has no correction to remove")
    before = format_rule(from_json(row.effective_expr))
    row.override_expr, row.override_is_none, row.override_note = None, False, None
    row.reviewed, row.reviewed_by, row.reviewed_at = False, None, None
    _audit(session, actor, "rule.revert", f"{row.course_code} {row.kind}", {"removed": before})
    bump_revision(session)
    title = session.get(CourseRow, row.course_code)
    return rule_out(row, title.title if title else row.course_code)


@router.get("/imports", summary="Program imports, newest first")
def imports(
    session: SessionDep, _admin: AdminDep, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[s.ImportRunOut]:
    rows = session.scalars(select(ImportRunRow).order_by(ImportRunRow.id.desc()).limit(limit))
    return [s.ImportRunOut.model_validate(row, from_attributes=True) for row in rows]


@router.get("/audit", summary="Admin actions, newest first (F9.3)")
def audit(
    session: SessionDep, _admin: AdminDep, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[s.AuditOut]:
    rows = session.scalars(select(AuditLogRow).order_by(AuditLogRow.id.desc()).limit(limit))
    return [s.AuditOut.model_validate(row, from_attributes=True) for row in rows]
