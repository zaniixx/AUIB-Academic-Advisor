"""Sign-in with an AUIB email address (F9.1).

The course and program data are only for AUIB students: every catalog and planning endpoint needs a
session (``require_student`` in deps.py). A session starts when a student enters the code emailed to
their university address, and lives in an HttpOnly cookie that only ``/api`` receives.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api import schemas as s
from app.api.deps import SESSION_COOKIE, SessionDep, SettingsDep, StudentDep
from app.services import auth, mail
from app.settings import Settings

router = APIRouter(prefix="/api/v1/auth", tags=["sign-in"])

# Codes asked for from one address (a visitor), per process, so one visitor cannot email many students.
_PER_ADDRESS_PER_HOUR = 10


class _Recent:
    """When each visitor last asked for codes, for the last hour."""

    def __init__(self) -> None:
        self._times: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: float = 3600) -> bool:
        now = time.monotonic()
        with self._lock:
            times = self._times.setdefault(key, deque())
            while times and now - times[0] > window:
                times.popleft()
            if len(times) >= limit:
                return False
            times.append(now)
            if len(self._times) > 10_000:
                for stale in [k for k, v in self._times.items() if not v or now - v[-1] > window]:
                    del self._times[stale]
            return True


_requests = _Recent()


def _refuse(error: auth.SignInError) -> HTTPException:
    headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
    return HTTPException(error.status, error.message, headers=headers)


@router.post(
    "/request-code",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Email a sign-in code to an AUIB address",
)
def request_code(
    body: s.CodeRequestIn, request: Request, db: SessionDep, settings: SettingsDep
) -> s.CodeSentOut:
    try:
        email = auth.check_email(body.email, settings.allowed_email_domains)
    except auth.SignInError as error:
        raise _refuse(error) from error
    visitor = request.client.host if request.client else "unknown"
    if not _requests.allow(visitor, _PER_ADDRESS_PER_HOUR):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many codes were asked for from this connection. Try again later.",
            headers={"Retry-After": "600"},
        )
    try:
        code = auth.issue_code(db, settings, email, auth.utcnow())
    except auth.SignInError as error:
        raise _refuse(error) from error
    try:
        mail.send_sign_in_code(settings, email, code)
    except mail.MailError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The email could not be sent. Please try again in a minute."
        ) from error
    return s.CodeSentOut(
        email=email,
        expires_in_minutes=settings.login_code_minutes,
        resend_after_seconds=int(auth.RESEND_AFTER.total_seconds()),
    )


@router.post("/verify", summary="Check the emailed code and start a session")
def verify(body: s.VerifyIn, response: Response, db: SessionDep, settings: SettingsDep) -> s.SignedInOut:
    try:
        email = auth.check_email(body.email, settings.allowed_email_domains)
        signed_in = auth.verify_code(db, settings, email, body.code, auth.utcnow())
    except auth.WrongCodeError as error:
        db.commit()  # the wrong attempt must count, even though the request fails
        raise _refuse(error) from error
    except auth.SignInError as error:
        raise _refuse(error) from error
    _set_cookie(response, settings, signed_in.token, settings.session_days * 86_400)
    return s.SignedInOut(email=signed_in.email, expires_at=signed_in.expires_at)


@router.get("/me", summary="The signed-in student")
def me(student: StudentDep) -> s.SignedInOut:
    return s.SignedInOut(email=student.email, expires_at=student.expires_at)


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT, summary="End this browser's session")
def sign_out(
    request: Request,
    response: Response,
    db: SessionDep,
    settings: SettingsDep,
    body: s.SignOutIn | None = None,
) -> None:
    auth.end_session(db, request.cookies.get(SESSION_COOKIE), everywhere=bool(body and body.everywhere))
    _set_cookie(response, settings, "", 0)


def _set_cookie(response: Response, settings: Settings, token: str, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        path="/api",
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
    )
