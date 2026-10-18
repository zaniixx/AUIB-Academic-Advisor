"""Admins and advisors (ADR 0009).

Staff sign in with their AUIB email like students; a role makes a signed-in address an admin or an
advisor. Only the master token (ADVISOR_ADMIN_TOKEN) adds or removes admins, and admins add or remove
advisors. Advisors have no extra rights until the advisor view exists (F5.3).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.api import admin_schemas as a
from app.api.deps import AdminDep, SessionDep, SettingsDep
from app.models import StaffRow
from app.services import auth, staff

router = APIRouter(prefix="/api/v1/admin", tags=["admin: people"])


def _out(row: StaffRow) -> a.StaffOut:
    return a.StaffOut(email=row.email, role=row.role, added_by=row.added_by, added_at=row.added_at)


@router.get("/me", summary="Who is using the admin page")
def whoami(actor: AdminDep) -> a.AdminMeOut:
    master = actor == staff.MASTER_ACTOR
    return a.AdminMeOut(actor=actor, via="master token" if master else "email", can_manage_admins=master)


@router.get("/staff", summary="Admins and advisors")
def list_people(session: SessionDep, _: AdminDep) -> list[a.StaffOut]:
    return [_out(row) for row in staff.list_staff(session)]


@router.put("/staff", summary="Give an AUIB address a role, or change it")
def grant(body: a.StaffIn, session: SessionDep, settings: SettingsDep, actor: AdminDep) -> a.StaffOut:
    try:
        email = auth.check_email(body.email, settings.allowed_email_domains)
        return _out(staff.grant(session, actor, email, body.role, manage_admins=actor == staff.MASTER_ACTOR))
    except auth.SignInError as error:
        raise HTTPException(error.status, error.message) from error
    except staff.StaffError as error:
        raise HTTPException(error.status, error.message) from error


@router.delete("/staff/{email}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove an admin or advisor")
def revoke(email: str, session: SessionDep, actor: AdminDep) -> Response:
    try:
        staff.revoke(session, actor, auth.normalize_email(email), manage_admins=actor == staff.MASTER_ACTOR)
    except staff.StaffError as error:
        raise HTTPException(error.status, error.message) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
