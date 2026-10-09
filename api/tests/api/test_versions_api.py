"""Program versions through the API: students follow the version in force when they joined (F0.4)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

CS = "casc-computer-science"
CS_2027 = f"{CS}-2027"
ADMIN = "/api/v1/admin"
HISTORY_FROM_FALL_2025 = [{"code": "CSC 101", "status": "completed", "term": "Fall 2025", "grade": "A"}]


def _draft(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": group["label"],
        "title": group["title"],
        "role": group["role"],
        "units_required": group["units_required"],
        "courses": group["courses"],
        "children": [_draft(child) for child in group["children"]],
    }


def _new_version(client: TestClient, headers: dict[str, str], **changes: object) -> dict[str, Any]:
    current = client.get(f"{ADMIN}/programs/{CS}", headers=headers).json()
    body = {
        "id": CS_2027,
        "name": "Computer Science",
        "kind": "major",
        "total_units": current["total_units"],
        "published": True,
        "accept_warnings": True,
        "family": CS,
        "valid_from": "fall 2027",
        "root": _draft(current["root"]),
        **changes,
    }
    response = client.post(f"{ADMIN}/programs", json=body, headers=headers)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def _catalog(client: TestClient, **student: object) -> dict[str, Any]:
    response = client.post("/api/v1/planner/plan", json={"program_id": CS, **student})
    assert response.status_code == 200, response.text
    info: dict[str, Any] = response.json()["catalog"]
    return info


def test_one_version_applies_to_every_student(client: TestClient) -> None:
    info = _catalog(client, attempts=HISTORY_FROM_FALL_2025)
    assert (info["program_id"], info["version_choice"], info["entry_term"]) == (CS, "only", "Fall 2025")
    assert (
        info["version_note"]
        == "These Computer Science requirements apply to every student; no other version is on file."
    )


def test_students_follow_the_version_in_force_when_they_joined(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    saved = _new_version(client, admin_headers)
    assert saved["saved"] is True
    assert (saved["program"]["family"], saved["program"]["valid_from"]) == (CS, "Fall 2027")

    # Students still choose one Computer Science, with both versions listed.
    majors = client.get("/api/v1/programs", params={"kind": "major"}).json()
    assert [m["id"] for m in majors] == [CS]
    assert [(v["id"], v["applies_to"]) for v in majors[0]["versions"]] == [
        (CS, "students who joined before Fall 2027"),
        (CS_2027, "students who joined from Fall 2027 on"),
    ]

    joined_2025 = _catalog(client, attempts=HISTORY_FROM_FALL_2025)
    assert (joined_2025["program_id"], joined_2025["version_choice"]) == (CS, "joined")
    assert joined_2025["version_note"] == (
        "Your first term at AUIB was Fall 2025, so you follow the Computer Science requirements for students "
        "who joined before Fall 2027."
    )
    assert [v["in_use"] for v in joined_2025["versions"]] == [True, False]

    # A new student starts in Spring 2027 (today is 8 October 2026), before the new version.
    new_student = _catalog(client)
    assert (new_student["program_id"], new_student["entry_term"]) == (CS, "Spring 2027")
    assert new_student["version_note"].startswith("You start in Spring 2027")

    joining_2027 = _catalog(client, entry_term="Fall 2027")
    assert joining_2027["program_id"] == CS_2027
    assert joining_2027["valid_from"] == "Fall 2027"

    # With the registrar's approval a student may follow the newer version.
    moved = _catalog(client, attempts=HISTORY_FROM_FALL_2025, program_version=CS_2027)
    assert (moved["program_id"], moved["version_choice"]) == (CS_2027, "chosen")
    wrong = client.post(
        "/api/v1/planner/plan", json={"program_id": CS, "program_version": "minor-psychology"}
    )
    assert wrong.status_code == 404


def test_versions_need_their_own_first_term_and_an_existing_program(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    _new_version(client, admin_headers)
    clash = _new_version(client, admin_headers, id=f"{CS}-2027b")
    assert clash["saved"] is False
    assert any("already applies from Fall 2027" in f["message"] for f in clash["findings"])
    orphan = _new_version(client, admin_headers, id=f"{CS}-x", family="no-such-program")
    assert orphan["saved"] is False
    assert any("no program 'no-such-program'" in f["message"] for f in orphan["findings"])
    wrong_kind = _new_version(
        client, admin_headers, id=f"{CS}-y", family="minor-psychology", valid_from="Fall 2030"
    )
    assert wrong_kind["saved"] is False
    assert any("is a minor" in f["message"] for f in wrong_kind["findings"])
