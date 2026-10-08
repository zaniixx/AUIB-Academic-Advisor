import json
import shutil
from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from app.importer.load import import_courses, import_package
from app.importer.package import load_courses, load_package
from app.models import CourseRow, ImportRunRow
from tests.conftest import COURSES_FILE, CS_PACKAGE, PSY_ID, TLD_ID

CS = "casc-computer-science"


def _rule_id(client: TestClient, headers: dict[str, str], course: str) -> int:
    rules = client.get("/api/v1/admin/rules", params={"show": "all", "q": course}, headers=headers).json()[
        "rules"
    ]
    return next(r["id"] for r in rules if r["course_code"] == course and r["kind"] == "pre")


def test_admin_needs_the_token(client: TestClient) -> None:
    assert client.get("/api/v1/admin/rules").status_code == 401
    assert client.get("/api/v1/admin/rules", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_admin_is_off_without_a_configured_token(make_client: Callable[..., TestClient]) -> None:
    client = make_client(admin_token=None)
    assert client.get("/api/v1/admin/rules", headers={"Authorization": "Bearer anything"}).status_code == 503


def test_review_queue_shows_rules_beside_their_source(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    listing = client.get("/api/v1/admin/rules", headers=admin_headers).json()
    assert listing["counts"]["all"] == 351
    assert listing["counts"]["needs_review"] == 351
    first = listing["rules"][0]
    assert first["source_text"]
    assert first["parsed_rule"]


def test_checking_a_rule(client: TestClient, admin_headers: dict[str, str]) -> None:
    ok = client.post(
        "/api/v1/admin/rules/check", json={"rule": "csc 390 and standing(junior)"}, headers=admin_headers
    ).json()
    assert ok == {
        "valid": True,
        "rule": "CSC 390 AND STANDING(junior)",
        "english": "CSC 390 and Junior standing (60+ credits)",
        "error": None,
        "position": None,
        "unknown_courses": [],
    }
    bad = client.post("/api/v1/admin/rules/check", json={"rule": "CSC 390 AND"}, headers=admin_headers).json()
    assert bad["valid"] is False
    assert bad["position"] is not None


def test_correction_changes_plans_is_audited_and_survives_reimport(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    rule_id = _rule_id(client, admin_headers, "CSC 391")
    body = {"rule": "CSC 390 AND STANDING(junior)", "note": "Internship II follows Internship I"}
    corrected = client.put(f"/api/v1/admin/rules/{rule_id}", json=body, headers=admin_headers).json()
    assert corrected["effective_rule"] == "CSC 390 AND STANDING(junior)"
    assert corrected["reviewed"] is True

    plan = client.post("/api/v1/planner/plan", json={"program_id": CS}).json()
    terms = {i["code"]: t["term"]["label"] for t in plan["terms"] for i in t["items"] if i["code"]}
    order = [t["term"]["label"] for t in plan["terms"]]
    assert order.index(terms["CSC 390"]) < order.index(terms["CSC 391"])

    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        import_courses(session, load_courses(COURSES_FILE), actor="test")
        import_package(session, load_package(CS_PACKAGE), actor="test", accept_warnings=True)
        session.commit()
    after = client.get("/api/v1/admin/rules", params={"show": "overridden"}, headers=admin_headers).json()
    assert [r["effective_rule"] for r in after["rules"]] == ["CSC 390 AND STANDING(junior)"]

    actions = [entry["action"] for entry in client.get("/api/v1/admin/audit", headers=admin_headers).json()]
    assert "rule.correct" in actions

    reverted = client.delete(f"/api/v1/admin/rules/{rule_id}/override", headers=admin_headers).json()
    assert reverted["effective_rule"] == "STANDING(junior)"


def test_invalid_correction_is_refused(client: TestClient, admin_headers: dict[str, str]) -> None:
    rule_id = _rule_id(client, admin_headers, "CSC 231")
    response = client.put(
        f"/api/v1/admin/rules/{rule_id}", json={"rule": "CSC 230 OR"}, headers=admin_headers
    )
    assert response.status_code == 422


def test_approving_a_rule(client: TestClient, admin_headers: dict[str, str]) -> None:
    rule_id = _rule_id(client, admin_headers, "CSC 231")
    approved = client.post(f"/api/v1/admin/rules/{rule_id}/approve", headers=admin_headers).json()
    assert approved["reviewed"] is True
    assert approved["reviewed_by"] == "admin"


def test_import_history_is_listed(client: TestClient, admin_headers: dict[str, str]) -> None:
    runs = client.get("/api/v1/admin/imports", headers=admin_headers).json()
    assert {run["program_id"] for run in runs} == {"course-catalog", CS, PSY_ID, TLD_ID}
    assert {run["status"] for run in runs} == {"imported"}


def test_reimport_creates_no_duplicates(client: TestClient) -> None:
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        before = session.query(CourseRow).count()
        catalog = import_courses(session, load_courses(COURSES_FILE), actor="test")
        program = import_package(session, load_package(CS_PACKAGE), actor="test", accept_warnings=True)
        session.commit()
        assert session.query(CourseRow).count() == before
    assert catalog.counts == {"courses_unchanged": 626, "rules_unchanged": 351}
    assert program.counts == {"groups": 15}


def test_broken_package_is_rejected_and_changes_nothing(client: TestClient, tmp_path: Path) -> None:
    package = tmp_path / "broken"
    shutil.copytree(CS_PACKAGE, package)
    requirements = json.loads((package / "requirements.json").read_text(encoding="utf-8"))
    requirements[2]["courses"].append("CSC 999")
    (package / "requirements.json").write_text(json.dumps(requirements), encoding="utf-8")
    meta = json.loads((package / "program.json").read_text(encoding="utf-8"))
    meta["id"] = "broken-program"
    (package / "program.json").write_text(json.dumps(meta), encoding="utf-8")

    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        result = import_package(session, load_package(package), actor="test")
        session.commit()
        assert result.status == "rejected"
        assert any("CSC 999" in f.message for f in result.validation.errors)
        assert (
            session.query(ImportRunRow).filter_by(program_id="broken-program", status="rejected").count() == 1
        )
    assert [p["id"] for p in client.get("/api/v1/programs", params={"kind": "major"}).json()] == [CS]
