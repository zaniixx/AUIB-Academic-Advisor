"""The app starts and works with no course data at all: admins add courses and programs in the admin page,
by hand or in bulk, and students can plan as soon as a program is published."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Base
from app.services import auth
from app.settings import Settings
from tests.api.conftest import ADMIN_TOKEN, DATABASE_URL, STUDENT_EMAIL
from tests.conftest import TODAY

ADMIN = "/api/v1/admin"
MASTER = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
COURSES = "code,title,credits,offered\nTST 101,First Steps,3,\nTST 102,Second Steps,3,\nTST 201,Field Work,3,summer\n"
MAJOR = {
    "id": "test-major",
    "name": "Test Major",
    "kind": "major",
    "total_units": 9,
    "published": True,
    "accept_warnings": True,
    "root": {
        "label": "Test Major",
        "units_required": 9,
        "children": [
            {
                "label": "Core",
                "role": "core",
                "units_required": 9,
                "courses": ["TST 101", "TST 102", "TST 201"],
            }
        ],
    },
}


@pytest.fixture
def empty_client() -> Iterator[TestClient]:
    """A signed-in student on a server whose database has no courses or programs."""
    settings = Settings(  # type: ignore[call-arg]
        environment="test", database_url=DATABASE_URL, admin_token=ADMIN_TOKEN, rate_limit_per_minute=1000
    )
    app = create_app(settings)
    Base.metadata.drop_all(app.state.engine)
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as session:
        token = auth.start_session(session, settings, STUDENT_EMAIL, auth.utcnow()).token
        session.commit()
    app.state.today = lambda: TODAY
    with TestClient(app) as client:
        client.cookies.set("advisor_session", token)
        yield client


def test_an_empty_server_is_ready_and_every_page_has_an_answer(empty_client: TestClient) -> None:
    ready = empty_client.get("/api/ready").json()
    assert ready["status"] == "ready" and ready["programs"] == 0
    assert empty_client.get("/api/v1/meta").status_code == 200
    assert empty_client.get("/api/v1/programs").json() == []
    assert empty_client.get("/api/v1/courses", params={"q": "csc"}).status_code == 200
    assert empty_client.get("/api/v1/courses/CSC 231").status_code == 404
    assert (
        empty_client.post("/api/v1/planner/plan", json={"program_id": "casc-computer-science"}).status_code
        == 404
    )
    for path in ("rules", "courses", "programs", "schedules", "imports", "audit", "staff", "me"):
        assert empty_client.get(f"{ADMIN}/{path}", headers=MASTER).status_code == 200, path


def test_an_admin_fills_an_empty_server_and_students_can_plan(empty_client: TestClient) -> None:
    saved = empty_client.post(
        f"{ADMIN}/courses/bulk", json={"text": COURSES, "dry_run": False}, headers=MASTER
    ).json()
    assert saved["applied"] is True and saved["counts"] == {"create": 3}
    built = empty_client.post(f"{ADMIN}/programs", json=MAJOR, headers=MASTER).json()
    assert built["saved"] is True

    assert [p["id"] for p in empty_client.get("/api/v1/programs").json()] == ["test-major"]
    assert empty_client.get("/api/ready").json()["programs"] == 1
    plan = empty_client.post("/api/v1/planner/plan", json={"program_id": "test-major"})
    assert plan.status_code == 200, plan.text
    planned = {item["code"] for term in plan.json()["terms"] for item in term["items"] if item.get("code")}
    assert planned == {"TST 101", "TST 102", "TST 201"}
