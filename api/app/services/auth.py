"""Sign-in with an AUIB email address (F9.1): one-time codes sent by email, then a browser session.

A student asks for a code for their university address; the code is emailed, and entering it starts a
session whose random token lives in an HttpOnly cookie. The database keeps only hashes: a keyed hash of
each code (so a copy of the database alone does not reveal codes) and a SHA-256 hash of each session
token. Codes expire within minutes, work once, allow a few wrong guesses, and a student can ask for
only a few per hour.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import LoginCodeRow, SessionRow
from app.settings import Settings

CODE_DIGITS = 6
MAX_ATTEMPTS = 5  # wrong codes before a code stops working
RESEND_AFTER = timedelta(seconds=60)
MAX_CODES_PER_HOUR = 5
KEEP_CODES = timedelta(days=1)  # used and expired codes are deleted after this
TOUCH_EVERY = timedelta(hours=1)  # how often a session's last-seen time is written

# A plain address: letters, digits and . _ % + - before the @, and a domain of letters, digits and -.
_EMAIL = re.compile(r"^[a-z0-9](?:[a-z0-9._%+-]{0,62}[a-z0-9])?@([a-z0-9-]+(?:\.[a-z0-9-]+)+)$")


class SignInError(Exception):
    """A refusal to show the student; ``status`` is the HTTP status to answer with."""

    status = 400

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class NotAllowedError(SignInError):
    status = 422


class TooManyError(SignInError):
    status = 429


class WrongCodeError(SignInError):
    """A wrong code; the attempt has been counted and must be committed before answering."""

    status = 400


@dataclass(frozen=True)
class SignedIn:
    token: str  # goes into the cookie; never stored
    email: str
    expires_at: datetime


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


def check_email(raw: str, domains: list[str]) -> str:
    """The normalized address, or NotAllowedError when it is not a university address."""
    email = normalize_email(raw)
    match = _EMAIL.match(email)
    if match is None:
        raise NotAllowedError("Enter an email address like name@" + domains[0])
    if match.group(1) not in domains:
        raise NotAllowedError(f"Use your AUIB email address (name@{domains[0]}).")
    return email


def issue_code(db: Session, settings: Settings, email: str, now: datetime) -> str:
    """Record a new sign-in code for ``email`` and return it, to be emailed. Earlier codes stop working."""
    _clean_up(db, now)
    recent = list(
        db.scalars(
            select(LoginCodeRow.created_at)
            .where(LoginCodeRow.email == email, LoginCodeRow.created_at > now - timedelta(hours=1))
            .order_by(LoginCodeRow.created_at)
        )
    )
    if recent:
        since_last = now - _aware(recent[-1])
        if since_last < RESEND_AFTER:
            wait = int((RESEND_AFTER - since_last).total_seconds()) + 1
            raise TooManyError(f"A code was sent less than a minute ago. Ask again in {wait} seconds.", wait)
    if len(recent) >= MAX_CODES_PER_HOUR:
        wait = int((_aware(recent[0]) + timedelta(hours=1) - now).total_seconds()) + 1
        raise TooManyError("Too many codes were sent to this address. Try again in an hour.", wait)
    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    db.add(
        LoginCodeRow(
            email=email,
            code_hash=_code_hash(settings, email, code),
            created_at=now,
            expires_at=now + timedelta(minutes=settings.login_code_minutes),
            attempts=0,
        )
    )
    db.flush()
    return code


def verify_code(db: Session, settings: Settings, email: str, code: str, now: datetime) -> SignedIn:
    """Start a session when ``code`` is the latest code sent to ``email``."""
    row = db.scalar(
        select(LoginCodeRow)
        .where(LoginCodeRow.email == email)
        .order_by(LoginCodeRow.created_at.desc())
        .limit(1)
    )
    if row is None or row.used_at is not None or _aware(row.expires_at) <= now:
        raise SignInError("This code has expired or was already used. Ask for a new one.")
    if row.attempts >= MAX_ATTEMPTS:
        raise SignInError("Too many wrong codes. Ask for a new one.")
    if not hmac.compare_digest(_code_hash(settings, email, code.strip()), row.code_hash):
        row.attempts += 1
        left = MAX_ATTEMPTS - row.attempts
        if left == 0:
            raise WrongCodeError("That code is not right, and it has now stopped working. Ask for a new one.")
        raise WrongCodeError(f"That code is not right. {left} more {'try' if left == 1 else 'tries'}.")
    row.used_at = now
    return start_session(db, settings, email, now)


def start_session(db: Session, settings: Settings, email: str, now: datetime) -> SignedIn:
    token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(days=settings.session_days)
    db.add(
        SessionRow(
            token_hash=_token_hash(token),
            email=email,
            created_at=now,
            expires_at=expires_at,
            last_seen_at=now,
        )
    )
    db.flush()
    return SignedIn(token, email, expires_at)


def find_session(db: Session, token: str | None, now: datetime) -> SessionRow | None:
    """The live session for a cookie's token, or None."""
    if not token or len(token) > 200:
        return None
    row = db.scalar(select(SessionRow).where(SessionRow.token_hash == _token_hash(token)))
    if row is None or _aware(row.expires_at) <= now:
        return None
    if now - _aware(row.last_seen_at) > TOUCH_EVERY:
        row.last_seen_at = now
    return row


def end_session(db: Session, token: str | None, everywhere: bool = False) -> None:
    """Sign this browser out; with ``everywhere``, every session and code of the same student too, so
    the server no longer holds their address at all (F9.2)."""
    if not token or len(token) > 200:
        return
    if everywhere:
        row = db.scalar(select(SessionRow).where(SessionRow.token_hash == _token_hash(token)))
        if row is not None:
            db.execute(delete(SessionRow).where(SessionRow.email == row.email))
            db.execute(delete(LoginCodeRow).where(LoginCodeRow.email == row.email))
            return
    db.execute(delete(SessionRow).where(SessionRow.token_hash == _token_hash(token)))


def counts(db: Session, now: datetime) -> dict[str, int]:
    """Live sessions and the distinct addresses behind them, for the operations page."""
    live = SessionRow.expires_at > now
    return {
        "sessions": db.scalar(select(func.count()).select_from(SessionRow).where(live)) or 0,
        "students": db.scalar(select(func.count(func.distinct(SessionRow.email))).where(live)) or 0,
    }


def _clean_up(db: Session, now: datetime) -> None:
    """Forget old codes and expired sessions, so nothing is kept longer than it is needed."""
    db.execute(delete(LoginCodeRow).where(LoginCodeRow.created_at < now - KEEP_CODES))
    db.execute(delete(SessionRow).where(SessionRow.expires_at < now))


def _code_hash(settings: Settings, email: str, code: str) -> str:
    return hmac.new(settings.code_key, f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(moment: datetime) -> datetime:
    """SQLite returns times without a zone; they are stored in UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)
