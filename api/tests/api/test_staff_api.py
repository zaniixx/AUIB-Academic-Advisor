"""Admins and advisors by AUIB email, granted with the master token (ADR 0009)."""

from fastapi.testclient import TestClient

from app.models import AuditLogRow
from app.services import auth
from tests.api.conftest import ADMIN_TOKEN

ADMIN = "/api/v1/admin"
MASTER = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
ADMIN_EMAIL = "registrar.admin@auib.edu.iq"
ADVISOR_EMAIL = "cs.advisor@auib.edu.iq"


def _signed_in(client: TestClient, email: str) -> TestClient:
    """Another browser on the same app, signed in as ``email`` (as if they entered their emailed code)."""
    app = client.app
    with app.state.session_factory() as session:  # type: ignore[attr-defined]
        token = auth.start_session(session, app.state.settings, email, auth.utcnow()).token  # type: ignore[attr-defined]
        session.commit()
    other = TestClient(app)
    other.cookies.set("advisor_session", token)
    return other


def test_the_master_token_adds_an_admin_who_then_works_by_email(client: TestClient) -> None:
    assert client.get(f"{ADMIN}/me", headers=MASTER).json() == {
        "actor": "master token",
        "via": "master token",
        "can_manage_admins": True,
    }
    added = client.put(
        f"{ADMIN}/staff", json={"email": " Registrar.Admin@AUIB.edu.iq ", "role": "admin"}, headers=MASTER
    )
    assert added.status_code == 200
    assert added.json()["email"] == ADMIN_EMAIL and added.json()["added_by"] == "master token"

    admin = _signed_in(client, ADMIN_EMAIL)
    assert admin.get("/api/v1/auth/me").json()["role"] == "admin"
    assert admin.get(f"{ADMIN}/me").json() == {
        "actor": ADMIN_EMAIL,
        "via": "email",
        "can_manage_admins": False,
    }
    rules = admin.get(f"{ADMIN}/rules", params={"show": "all"}).json()["rules"]
    approved = admin.post(f"{ADMIN}/rules/{rules[0]['id']}/approve")
    assert approved.status_code == 200 and approved.json()["reviewed_by"] == ADMIN_EMAIL  # audited by name


def test_admins_manage_advisors_but_only_the_master_token_manages_admins(client: TestClient) -> None:
    client.put(f"{ADMIN}/staff", json={"email": ADMIN_EMAIL, "role": "admin"}, headers=MASTER)
    admin = _signed_in(client, ADMIN_EMAIL)

    assert admin.put(f"{ADMIN}/staff", json={"email": ADVISOR_EMAIL, "role": "advisor"}).status_code == 200
    advisor = _signed_in(client, ADVISOR_EMAIL)
    assert advisor.get("/api/v1/auth/me").json()["role"] == "advisor"
    assert advisor.get(f"{ADMIN}/rules").status_code == 403  # advisors have no admin rights (yet: F5.3)
    assert advisor.get("/api/v1/programs").status_code == 200  # and use the app like a student

    refused = admin.put(f"{ADMIN}/staff", json={"email": ADVISOR_EMAIL, "role": "admin"})
    assert refused.status_code == 403 and "master token" in refused.json()["detail"]
    assert (
        admin.put(f"{ADMIN}/staff", json={"email": "new.admin@auib.edu.iq", "role": "admin"}).status_code
        == 403
    )
    assert admin.delete(f"{ADMIN}/staff/{ADMIN_EMAIL}").status_code == 403
    assert admin.delete(f"{ADMIN}/staff/{ADVISOR_EMAIL}").status_code == 204
    assert advisor.get("/api/v1/auth/me").json()["role"] is None

    # Removing an admin takes effect at once, without signing them out.
    assert client.delete(f"{ADMIN}/staff/{ADMIN_EMAIL}", headers=MASTER).status_code == 204
    assert admin.get(f"{ADMIN}/rules").status_code == 403
    assert client.get(f"{ADMIN}/staff", headers=MASTER).json() == []


def test_only_auib_addresses_can_be_staff_and_every_change_is_audited(client: TestClient) -> None:
    outside = client.put(
        f"{ADMIN}/staff", json={"email": "someone@gmail.com", "role": "advisor"}, headers=MASTER
    )
    assert outside.status_code == 422
    assert (
        client.put(
            f"{ADMIN}/staff", json={"email": ADVISOR_EMAIL, "role": "boss"}, headers=MASTER
        ).status_code
        == 422
    )
    assert client.delete(f"{ADMIN}/staff/nobody@auib.edu.iq", headers=MASTER).status_code == 404
    assert (
        client.put(f"{ADMIN}/staff", json={"email": "someone@auib.edu.iq", "role": "advisor"}).status_code
        == 403
    )

    client.put(f"{ADMIN}/staff", json={"email": ADVISOR_EMAIL, "role": "advisor"}, headers=MASTER)
    client.put(f"{ADMIN}/staff", json={"email": ADVISOR_EMAIL, "role": "admin"}, headers=MASTER)
    client.delete(f"{ADMIN}/staff/{ADVISOR_EMAIL}", headers=MASTER)
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        entries = [
            (row.actor, row.action, row.target, row.detail)
            for row in session.query(AuditLogRow)
            .filter(AuditLogRow.action.like("staff.%"))
            .order_by(AuditLogRow.id)
        ]
    assert entries == [
        ("master token", "staff.grant", ADVISOR_EMAIL, {"role": "advisor", "before": None}),
        ("master token", "staff.grant", ADVISOR_EMAIL, {"role": "admin", "before": "advisor"}),
        ("master token", "staff.revoke", ADVISOR_EMAIL, {"role": "admin"}),
    ]
