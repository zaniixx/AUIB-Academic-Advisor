"""Admins and advisors (ADR 0009): AUIB addresses with a role.

Staff sign in like students, with a code emailed to their address (F9.1), so an address is verified by
its owner signing in, not by the person who adds it. The role is looked up on every request, so removing
someone takes effect at once. Only the master token (ADVISOR_ADMIN_TOKEN) adds or removes admins; a
signed-in admin adds or removes advisors. Every change is written to the audit log.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLogRow, StaffRow, utcnow

Role = Literal["admin", "advisor"]
ROLES: tuple[Role, ...] = ("admin", "advisor")
MASTER_ACTOR = "master token"


class StaffError(ValueError):
    """A change to staff that is not allowed; ``status`` is the HTTP status to answer with."""

    def __init__(self, message: str, status: int = 403) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def role_of(session: Session, email: str) -> Role | None:
    row = session.get(StaffRow, email)
    return row.role if row is not None and row.role in ROLES else None


def list_staff(session: Session) -> list[StaffRow]:
    return list(session.scalars(select(StaffRow).order_by(StaffRow.role, StaffRow.email)))


def _may_change(manage_admins: bool, *roles: str | None) -> None:
    if "admin" in roles and not manage_admins:
        raise StaffError("Only the holder of the master token can add or remove admins.")


def grant(session: Session, actor: str, email: str, role: Role, *, manage_admins: bool) -> StaffRow:
    """Give ``email`` a role, or change its role. ``email`` must already be a checked AUIB address.
    ``manage_admins`` is true for the master token and for the server's command line."""
    row = session.get(StaffRow, email)
    _may_change(manage_admins, role, row.role if row else None)
    before = row.role if row else None
    if row is None:
        row = StaffRow(email=email, role=role, added_by=actor, added_at=utcnow())
        session.add(row)
    else:
        row.role = role
    if before != role:
        session.add(
            AuditLogRow(
                actor=actor, action="staff.grant", target=email, detail={"role": role, "before": before}
            )
        )
    return row


def revoke(session: Session, actor: str, email: str, *, manage_admins: bool) -> None:
    row = session.get(StaffRow, email)
    if row is None:
        raise StaffError(f"{email} is not an admin or advisor.", status=404)
    _may_change(manage_admins, row.role)
    session.delete(row)
    session.add(AuditLogRow(actor=actor, action="staff.revoke", target=email, detail={"role": row.role}))
