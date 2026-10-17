"""Sign-in with an AUIB email address (F9.1): only signed-in students reach course and program data."""

from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import LoginCodeRow, SessionRow
from app.services import auth, mail

AUTH = "/api/v1/auth"
EMAIL = "new.student@auib.edu.iq"


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Codes "emailed" during a test, as (address, code)."""
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(mail, "send_sign_in_code", lambda _settings, to, code: sent.append((to, code)))
    return sent


def _sign_in(client: TestClient, outbox: list[tuple[str, str]], email: str = EMAIL) -> None:
    assert client.post(f"{AUTH}/request-code", json={"email": email}).status_code == 202
    code = outbox[-1][1]
    assert client.post(f"{AUTH}/verify", json={"email": email, "code": code}).status_code == 200


def test_course_and_program_data_need_a_signed_in_student(anonymous_client: TestClient) -> None:
    for method, path in [
        ("GET", "/api/v1/meta"),
        ("GET", "/api/v1/programs"),
        ("GET", "/api/v1/programs/casc-computer-science"),
        ("GET", "/api/v1/courses?q=csc"),
        ("GET", "/api/v1/courses/CSC%20231"),
        ("POST", "/api/v1/planner/plan"),
        ("POST", "/api/v1/history/parse"),
    ]:
        response = anonymous_client.request(method, path, json={"program_id": "casc-computer-science"})
        assert response.status_code == 401, path
        assert response.json() == {"detail": "Sign in with your AUIB email address to continue."}
        assert "CSC" not in response.text
    # Health checks and sign-in stay open.
    assert anonymous_client.get("/api/health").status_code == 200
    assert anonymous_client.get("/api/ready").status_code == 200
    assert anonymous_client.get(f"{AUTH}/me").status_code == 401


def test_a_student_signs_in_with_an_emailed_code(
    anonymous_client: TestClient, outbox: list[tuple[str, str]]
) -> None:
    sent = anonymous_client.post(f"{AUTH}/request-code", json={"email": "  New.Student@AUIB.edu.iq "})
    assert sent.status_code == 202
    assert sent.json() == {"email": EMAIL, "expires_in_minutes": 10, "resend_after_seconds": 60}
    assert len(outbox) == 1 and outbox[0][0] == EMAIL and outbox[0][1].isdigit() and len(outbox[0][1]) == 6

    verified = anonymous_client.post(f"{AUTH}/verify", json={"email": EMAIL, "code": outbox[0][1]})
    assert verified.status_code == 200
    assert verified.json()["email"] == EMAIL
    cookie = verified.headers["set-cookie"]
    assert "advisor_session=" in cookie and "HttpOnly" in cookie and "Path=/api" in cookie
    assert "samesite=lax" in cookie.lower()

    assert anonymous_client.get("/api/v1/programs").status_code == 200
    assert anonymous_client.get(f"{AUTH}/me").json()["email"] == EMAIL

    assert anonymous_client.post(f"{AUTH}/sign-out").status_code == 204
    assert anonymous_client.get("/api/v1/programs").status_code == 401


@pytest.mark.parametrize(
    "email",
    ["someone@gmail.com", "x@mail.auib.edu.iq", "x@auib.edu.iq.evil.com", "not-an-email", "a@b@auib.edu.iq"],
)
def test_only_university_addresses_get_a_code(
    anonymous_client: TestClient, outbox: list[tuple[str, str]], email: str
) -> None:
    response = anonymous_client.post(f"{AUTH}/request-code", json={"email": email})
    assert response.status_code == 422
    assert "auib.edu.iq" in response.json()["detail"]
    assert outbox == []


def test_wrong_codes_are_counted_and_a_code_works_once(
    anonymous_client: TestClient, outbox: list[tuple[str, str]]
) -> None:
    anonymous_client.post(f"{AUTH}/request-code", json={"email": EMAIL})
    code = outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    first = anonymous_client.post(f"{AUTH}/verify", json={"email": EMAIL, "code": wrong})
    assert first.status_code == 400
    assert first.json()["detail"] == "That code is not right. 4 more tries."
    assert anonymous_client.post(f"{AUTH}/verify", json={"email": EMAIL, "code": code}).status_code == 200
    again = anonymous_client.post(f"{AUTH}/verify", json={"email": EMAIL, "code": code})
    assert again.status_code == 400
    assert "already used" in again.json()["detail"]


def test_five_wrong_codes_stop_the_code(anonymous_client: TestClient, outbox: list[tuple[str, str]]) -> None:
    anonymous_client.post(f"{AUTH}/request-code", json={"email": EMAIL})
    code = outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        anonymous_client.post(f"{AUTH}/verify", json={"email": EMAIL, "code": wrong})
    late = anonymous_client.post(f"{AUTH}/verify", json={"email": EMAIL, "code": code})
    assert late.status_code == 400
    assert late.json()["detail"] == "Too many wrong codes. Ask for a new one."


def test_codes_expire_and_cannot_be_asked_for_too_often(
    anonymous_client: TestClient, outbox: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    anonymous_client.post(f"{AUTH}/request-code", json={"email": EMAIL})
    soon = anonymous_client.post(f"{AUTH}/request-code", json={"email": EMAIL})
    assert soon.status_code == 429
    assert 1 <= int(soon.headers["retry-after"]) <= 61
    code = outbox[-1][1]
    later = auth.utcnow() + timedelta(minutes=11)
    monkeypatch.setattr(auth, "utcnow", lambda: later)
    expired = anonymous_client.post(f"{AUTH}/verify", json={"email": EMAIL, "code": code})
    assert expired.status_code == 400
    assert "expired" in expired.json()["detail"]


def test_only_hashes_are_stored(
    make_client: Callable[..., TestClient], outbox: list[tuple[str, str]]
) -> None:
    client = make_client(signed_in=False)
    _sign_in(client, outbox)
    code = outbox[-1][1]
    token = client.cookies.get("advisor_session")
    assert token
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        stored_code = db.scalar(select(LoginCodeRow).where(LoginCodeRow.email == EMAIL))
        stored_session = db.scalar(select(SessionRow).where(SessionRow.email == EMAIL))
    assert stored_code is not None and code not in stored_code.code_hash
    assert stored_session is not None and stored_session.token_hash != token


def test_an_expired_session_no_longer_works(
    anonymous_client: TestClient, outbox: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _sign_in(anonymous_client, outbox)
    later = auth.utcnow() + timedelta(days=31)
    monkeypatch.setattr(auth, "utcnow", lambda: later)
    assert anonymous_client.get("/api/v1/programs").status_code == 401


def test_signing_out_everywhere_removes_the_address_from_the_server(
    make_client: Callable[..., TestClient], outbox: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    laptop = make_client(signed_in=False)
    _sign_in(laptop, outbox)
    phone = TestClient(laptop.app)
    later = auth.utcnow() + timedelta(minutes=2)  # the next code may be sent after a minute
    monkeypatch.setattr(auth, "utcnow", lambda: later)
    _sign_in(phone, outbox)
    assert phone.get("/api/v1/programs").status_code == 200

    assert laptop.post(f"{AUTH}/sign-out", json={"everywhere": True}).status_code == 204
    assert phone.get("/api/v1/programs").status_code == 401
    with laptop.app.state.session_factory() as db:  # type: ignore[attr-defined]
        assert db.scalar(select(SessionRow).where(SessionRow.email == EMAIL)) is None
        assert db.scalar(select(LoginCodeRow).where(LoginCodeRow.email == EMAIL)) is None
