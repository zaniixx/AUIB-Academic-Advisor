"""Editing the catalog in the admin page: courses, bulk uploads, programs, term schedules, backups."""

from __future__ import annotations

import base64
import gzip
import io
import json
import zipfile
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.importer.load import import_courses, import_package
from app.importer.package import CourseList, load_courses, load_package
from app.models import AuditLogRow, CourseRow, ProgramRow
from app.services.backup import BackupError, encrypt, export_data, read_backup, restore_data
from tests.api.conftest import build_app
from tests.conftest import COURSES_FILE, CS_PACKAGE

CS = "casc-computer-science"
ADMIN = "/api/v1/admin"


def _session(client: TestClient) -> Any:
    return client.app.state.session_factory()  # type: ignore[attr-defined]


def _audit_actions(client: TestClient) -> list[str]:
    with _session(client) as session:
        return [row.action for row in session.query(AuditLogRow).order_by(AuditLogRow.id)]


def _plan(client: TestClient, **extra: object) -> dict[str, Any]:
    response = client.post("/api/v1/planner/plan", json={"program_id": CS, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def test_catalog_editing_needs_the_token(client: TestClient) -> None:
    assert client.get(f"{ADMIN}/courses").status_code == 401
    assert client.post(f"{ADMIN}/backup", json={"passphrase": "x" * 20}).status_code == 401
    assert client.get(f"{ADMIN}/programs", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_add_a_course_by_hand(client: TestClient, admin_headers: dict[str, str]) -> None:
    body = {
        "code": "csc 395",
        "title": "Special Topics in Machine Learning",
        "units": 3,
        "description": "Selected topics. Prerequisite: CSC 231.",
        "offered_terms": ["fall"],
    }
    created = client.post(f"{ADMIN}/courses", json=body, headers=admin_headers)
    assert created.status_code == 201, created.text
    course = created.json()
    assert course["code"] == "CSC 395"
    assert course["origin"] == "admin"
    # Its prerequisite is read from the description, like an imported course's, and waits for review.
    assert [(r["kind"], r["effective_rule"], r["reviewed"]) for r in course["rules"]] == [
        ("pre", "CSC 231", False)
    ]
    assert client.post(f"{ADMIN}/courses", json=body, headers=admin_headers).status_code == 409

    found = client.get("/api/v1/courses", params={"q": "CSC 395"}).json()
    assert [c["code"] for c in found["courses"]] == ["CSC 395"]
    assert client.get("/api/v1/courses/CSC 395").json()["offered_terms"] == ["fall"]
    assert "course.create" in _audit_actions(client)


def test_an_edit_survives_reimport_and_can_be_undone(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    original = client.get(f"{ADMIN}/courses/CSC 231", headers=admin_headers).json()
    changed = {
        "title": "Data Structures and Algorithms",
        "units": original["units"],
        "description": original["description"],
        "component": original["component"],
        "offered_terms": original["offered_terms"],
        "notices": original["notices"],
    }
    edited = client.put(f"{ADMIN}/courses/CSC 231", json=changed, headers=admin_headers).json()
    assert edited["admin_edited"] is True
    assert edited["imported_values"]["title"] == "Data Structure"

    # Importing the same files keeps the edit and flags nothing.
    with _session(client) as session:
        import_courses(session, load_courses(COURSES_FILE), actor="test")
        session.commit()
    again = client.get(f"{ADMIN}/courses/CSC 231", headers=admin_headers).json()
    assert again["title"] == "Data Structures and Algorithms"
    assert again["source_changed"] is False

    # When the files change, the edit still stands and the course is flagged.
    files = load_courses(COURSES_FILE)
    raw = {code: dict(values) for code, values in files.raw_courses.items()}
    raw["CSC 231"]["title"] = "Data Structure (revised)"
    with _session(client) as session:
        import_courses(session, CourseList(files.path, raw), actor="test")
        session.commit()
    flagged = client.get(f"{ADMIN}/courses", params={"show": "source_changed"}, headers=admin_headers).json()
    assert [c["code"] for c in flagged["courses"]] == ["CSC 231"]
    assert client.get("/api/v1/courses/CSC 231").json()["title"] == "Data Structures and Algorithms"

    reverted = client.post(f"{ADMIN}/courses/CSC 231/revert", headers=admin_headers).json()
    assert reverted["title"] == "Data Structure (revised)"
    assert reverted["admin_edited"] is False
    assert reverted["source_changed"] is False


def test_hidden_courses_are_not_shown_or_planned(client: TestClient, admin_headers: dict[str, str]) -> None:
    hidden = client.put(f"{ADMIN}/courses/CSC 101/hidden", json={"hidden": True}, headers=admin_headers)
    assert hidden.json()["hidden"] is True
    assert client.get("/api/v1/courses/CSC 101").status_code == 404
    assert "CSC 101" not in {
        c["code"] for c in client.get("/api/v1/courses", params={"q": "CSC 1"}).json()["courses"]
    }
    plan = _plan(client)
    planned = {item["code"] for term in plan["terms"] for item in term["items"]}
    assert "CSC 101" not in planned
    assert "CSC 101" in {item["code"] for item in plan["unscheduled"]}
    messages = [issue["message"] for issue in plan["issues"]]
    assert "CSC 101 could not be scheduled because it is not offered at the moment." in messages
    # A student who already passed it keeps the credit.
    passed = _plan(
        client, attempts=[{"code": "CSC 101", "status": "completed", "term": "Fall 2025", "grade": "A"}]
    )
    assert passed["progress"]["completed_units"] == 3

    client.put(f"{ADMIN}/courses/CSC 101/hidden", json={"hidden": False}, headers=admin_headers)
    assert client.get("/api/v1/courses/CSC 101").status_code == 200
    assert [a for a in _audit_actions(client) if a.startswith("course.")] == ["course.hide", "course.show"]


def test_hidden_programs_are_not_offered(client: TestClient, admin_headers: dict[str, str]) -> None:
    client.put(f"{ADMIN}/programs/minor-psychology/hidden", json={"hidden": True}, headers=admin_headers)
    minors = {p["id"] for p in client.get("/api/v1/programs", params={"kind": "minor"}).json()}
    assert "minor-psychology" not in minors
    response = client.post("/api/v1/planner/plan", json={"program_id": CS, "minor_id": "minor-psychology"})
    assert response.status_code == 404
    listing = {p["id"]: p for p in client.get(f"{ADMIN}/programs", headers=admin_headers).json()}
    assert listing["minor-psychology"]["hidden"] is True


def test_rules_added_by_an_admin(client: TestClient, admin_headers: dict[str, str]) -> None:
    added = client.post(
        f"{ADMIN}/courses/CSC 231/rules",
        json={"kind": "co", "rule": "MAT 112", "note": "Department asked for it"},
        headers=admin_headers,
    )
    assert added.status_code == 201, added.text
    rule = added.json()
    assert (rule["effective_rule"], rule["source_text"], rule["reviewed"]) == ("MAT 112", "", True)
    assert (
        client.post(
            f"{ADMIN}/courses/CSC 231/rules", json={"kind": "co", "rule": "MAT 111"}, headers=admin_headers
        ).status_code
        == 409
    )
    public = client.get("/api/v1/courses/CSC 231").json()
    assert "co" in {r["kind"] for r in public["rules"]}

    # A rule read from the SIS description is corrected, not deleted.
    parsed = next(
        r
        for r in client.get(f"{ADMIN}/courses/CSC 231", headers=admin_headers).json()["rules"]
        if r["kind"] == "pre"
    )
    assert client.delete(f"{ADMIN}/rules/{parsed['id']}", headers=admin_headers).status_code == 409
    assert client.delete(f"{ADMIN}/rules/{rule['id']}", headers=admin_headers).status_code == 204
    assert "co" not in {r["kind"] for r in client.get("/api/v1/courses/CSC 231").json()["rules"]}


BULK = (
    "Course Code,Title,Credits,Offered\n"
    "CSC 396,Applied Cryptography,3,Fall; Spring\n"
    "CSC 231,,4,\n"
    "CSC 101,,,\n"
    "BADCODE,Nope,3,\n"
    "CSC 397,Research Seminar,two,\n"
)


def test_bulk_courses_preview_then_save(client: TestClient, admin_headers: dict[str, str]) -> None:
    preview = client.post(f"{ADMIN}/courses/bulk", json={"text": BULK}, headers=admin_headers).json()
    assert preview["applied"] is False
    assert preview["columns"] == ["course_code", "title", "credits", "offered"]
    assert preview["counts"] == {"create": 1, "update": 1, "unchanged": 1, "error": 2}
    rows = {row["line"]: row for row in preview["rows"]}
    assert rows[2]["action"] == "create"
    assert rows[3]["messages"] == ["credits: 3 → 4"]  # blank cells keep the current values
    assert "not a course code" in rows[5]["messages"][0]
    assert rows[6]["messages"] == ["Credits must be a number, not 'two'"]
    assert client.get("/api/v1/courses/CSC 396").status_code == 404  # a preview saves nothing

    # Saving is all or nothing: rows with problems block it.
    refused = client.post(
        f"{ADMIN}/courses/bulk", json={"text": BULK, "dry_run": False}, headers=admin_headers
    )
    assert refused.status_code == 422
    fixed = "\n".join(line for line in BULK.splitlines() if not line.startswith(("BADCODE", "CSC 397")))
    saved = client.post(
        f"{ADMIN}/courses/bulk", json={"text": fixed, "dry_run": False}, headers=admin_headers
    ).json()
    assert saved["applied"] is True
    assert client.get("/api/v1/courses/CSC 396").json()["offered_terms"] == ["fall", "spring"]
    assert client.get("/api/v1/courses/CSC 231").json()["units"] == 4
    assert "course.bulk" in _audit_actions(client)


def test_bulk_courses_from_a_spreadsheet_paste(client: TestClient, admin_headers: dict[str, str]) -> None:
    pasted = "code\ttitle\tunits\thidden\nCSC 398\tCapstone Studio\t3\tno\nCSC 101\t\t\tyes\n"
    preview = client.post(f"{ADMIN}/courses/bulk", json={"text": pasted}, headers=admin_headers).json()
    assert preview["counts"] == {"create": 1, "update": 1}
    assert {row["code"]: row["messages"] for row in preview["rows"]}["CSC 101"] == ["hidden"]


def _xlsx(rows: list[list[str | int]]) -> str:
    """A minimal .xlsx with one sheet, shared strings and numbers, in base64."""
    strings: list[str] = []
    cells = []
    for r, row in enumerate(rows, start=1):
        parts = []
        for c, value in enumerate(row):
            ref = f"{chr(65 + c)}{r}"
            if isinstance(value, int):
                parts.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                strings.append(value)
                parts.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
        cells.append(f'<row r="{r}">{"".join(parts)}</row>')
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{main}" xmlns:r="{rel}"><sheets><sheet name="Courses" sheetId="1" r:id="rId9"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId9" Type="{rel}/worksheet" Target="worksheets/data.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            f'<sst xmlns="{main}">' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>",
        )
        archive.writestr(
            "xl/worksheets/data.xml",
            f'<worksheet xmlns="{main}"><sheetData>{"".join(cells)}</sheetData></worksheet>',
        )
    return base64.b64encode(buffer.getvalue()).decode()


def test_bulk_courses_from_an_xlsx_file(client: TestClient, admin_headers: dict[str, str]) -> None:
    sheet = _xlsx([["Code", "Title", "Units"], ["CSC 399", "Independent Study", 3]])
    preview = client.post(f"{ADMIN}/courses/bulk", json={"xlsx_base64": sheet}, headers=admin_headers).json()
    assert preview["counts"] == {"create": 1}
    assert preview["rows"][0]["code"] == "CSC 399"


def test_a_workbook_with_a_dtd_is_refused(client: TestClient, admin_headers: dict[str, str]) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "xl/worksheets/sheet1.xml", '<!DOCTYPE x [<!ENTITY a "aaaa">]><worksheet>&a;</worksheet>'
        )
    body = {"xlsx_base64": base64.b64encode(buffer.getvalue()).decode()}
    response = client.post(f"{ADMIN}/courses/bulk", json=body, headers=admin_headers)
    assert response.status_code == 422
    assert "document type declaration" in response.json()["detail"]


MINOR = {
    "id": "minor-computing",
    "name": "Computing",
    "kind": "minor",
    "total_units": 9,
    "published": True,
    "root": {
        "label": "Minor in Computing",
        "units_required": 9,
        "children": [
            {"label": "Computing minor: CSC 231", "role": "core", "units_required": 3, "courses": ["csc231"]},
            {
                "label": "Computing minor: 2 of 3 electives",
                "role": "other",
                "units_required": 6,
                "courses": ["CSC 313", "CSC 333", "CSC 345"],
            },
        ],
    },
}


def test_build_a_minor_by_hand_and_plan_with_it(client: TestClient, admin_headers: dict[str, str]) -> None:
    broken = {
        **MINOR,
        "root": {**MINOR["root"], "children": [{"label": "X", "units_required": 3, "courses": ["ZZZ 101"]}]},
    }
    check = client.post(f"{ADMIN}/programs/check", json=broken, headers=admin_headers).json()
    assert check["ok"] is False
    assert any("missing from the course catalog" in f["message"] for f in check["findings"])

    # The catalog year is not set, which is a warning: publishing needs the admin's consent.
    assert client.post(f"{ADMIN}/programs", json=MINOR, headers=admin_headers).status_code == 409
    saved = client.post(
        f"{ADMIN}/programs", json={**MINOR, "accept_warnings": True}, headers=admin_headers
    ).json()
    assert saved["saved"] is True
    assert saved["program"]["origin"] == "admin"
    assert [g["label"] for g in saved["program"]["root"]["children"]] == [
        "Computing minor: CSC 231",
        "Computing minor: 2 of 3 electives",
    ]
    assert "minor-computing" in {
        p["id"] for p in client.get("/api/v1/programs", params={"kind": "minor"}).json()
    }
    plan = _plan(client, minor_id="minor-computing")
    assert plan["minor"]["name"] == "Computing"
    assert (
        client.post(
            f"{ADMIN}/programs", json={**MINOR, "accept_warnings": True}, headers=admin_headers
        ).status_code
        == 409
    )


def test_a_program_edited_here_is_kept_by_imports(client: TestClient, admin_headers: dict[str, str]) -> None:
    current = client.get(f"{ADMIN}/programs/{CS}", headers=admin_headers).json()
    assert current["standard_terms"] == 8
    assert _plan(client)["on_time_term"]["label"] == "Fall 2030"

    def draft(group: dict[str, Any]) -> dict[str, Any]:
        return {
            "label": group["label"],
            "title": group["title"],
            "role": group["role"],
            "units_required": group["units_required"],
            "courses": group["courses"],
            "children": [draft(child) for child in group["children"]],
        }

    body = {
        "id": CS,
        "name": "Computer Science (edited)",
        "kind": "major",
        "total_units": current["total_units"],
        "standard_terms": 10,
        "published": True,
        "accept_warnings": True,
        "root": draft(current["root"]),
    }
    saved = client.put(f"{ADMIN}/programs/{CS}", json=body, headers=admin_headers).json()
    assert saved["saved"] is True
    assert saved["program"]["admin_edited"] is True
    assert saved["program"]["standard_terms"] == 10
    edited = _plan(client)
    assert edited["catalog"]["program_name"] == "Computer Science (edited)"
    assert edited["on_time_term"]["label"] == "Fall 2031"  # ten regular semesters instead of eight

    with _session(client) as session:
        refused = import_package(session, load_package(CS_PACKAGE), actor="test", accept_warnings=True)
        session.commit()
    assert refused.status == "rejected"
    assert _plan(client)["catalog"]["program_name"] == "Computer Science (edited)"
    with _session(client) as session:
        replaced = import_package(
            session, load_package(CS_PACKAGE), actor="test", accept_warnings=True, replace_admin_edits=True
        )
        session.commit()
        assert replaced.status == "imported"
        assert session.get(ProgramRow, CS).admin_edited is False
    assert _plan(client)["catalog"]["program_name"] == "Computer Science"


def test_a_term_schedule_decides_what_is_planned_that_term(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    before = _plan(client)
    first = before["terms"][0]
    assert first["term"]["label"] == "Spring 2027"
    # F1.8: with no schedule published, no term's offerings are confirmed.
    assert not any(term["schedule_published"] for term in before["terms"])
    planned = [item["code"] for item in first["items"] if item["code"]]
    left_out = planned[0]
    on_schedule = planned[1:]
    lines = ["Subject,Catalog Nbr,Section,Days,Start,End,Instructor"]
    lines += [f"{code.split()[0]},{code.split()[1]},01,MW,09:00,10:15,Staff" for code in on_schedule]
    lines.append("XYZ,999,01,TR,11:00,12:15,Staff")  # not in the catalog: skipped and listed
    body = {"term": "Spring 2027", "text": "\n".join(lines)}

    preview = client.post(f"{ADMIN}/schedules", json=body, headers=admin_headers).json()
    assert preview["applied"] is False
    assert preview["counts"] == {"sections": len(on_schedule), "courses": len(on_schedule), "skipped": 1}
    assert preview["rows"][0]["code"] == "XYZ 999"

    saved = client.post(f"{ADMIN}/schedules", json={**body, "dry_run": False}, headers=admin_headers).json()
    assert saved["applied"] is True
    after = _plan(client)
    spring = next(t for t in after["terms"] if t["term"]["label"] == "Spring 2027")
    assert left_out not in {item["code"] for item in spring["items"]}
    assert spring["schedule_published"] is True
    assert [t["term"]["label"] for t in after["terms"] if t["schedule_published"]] == ["Spring 2027"]
    assert left_out not in {e["course"]["code"] for e in after["eligible_next_term"]}
    assert any("published course schedule" in line for line in after["assumptions"])

    sections = client.get(f"/api/v1/courses/{on_schedule[0]}").json()["offerings"]
    assert sections[0]["term"]["label"] == "Spring 2027"
    assert sections[0]["sections"][0]["time"] == "09:00–10:15"
    listing = client.get(f"{ADMIN}/schedules", headers=admin_headers).json()
    assert listing[0]["sections"] == len(on_schedule)

    assert client.delete(f"{ADMIN}/schedules/2027/spring", headers=admin_headers).status_code == 204
    assert _plan(client)["terms"][0]["items"] == before["terms"][0]["items"]
    assert {"schedule.upload", "schedule.delete"} <= set(_audit_actions(client))


def test_encrypted_backup_round_trip(client: TestClient, admin_headers: dict[str, str]) -> None:
    assert (
        client.post(f"{ADMIN}/backup", json={"passphrase": "short"}, headers=admin_headers).status_code == 422
    )
    client.put(f"{ADMIN}/courses/CSC 101/hidden", json={"hidden": True}, headers=admin_headers)
    passphrase = "correct horse battery staple"
    response = client.post(f"{ADMIN}/backup", json={"passphrase": passphrase}, headers=admin_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert "auib-advisor-backup-" in response.headers["content-disposition"]
    blob = response.content
    assert b"CSC 101" not in blob  # encrypted, not just compressed

    with pytest.raises(BackupError, match="Wrong passphrase"):
        read_backup(blob, "not the passphrase")
    tampered = blob[:-1] + bytes([blob[-1] ^ 1])
    with pytest.raises(BackupError):
        read_backup(tampered, passphrase)

    data = read_backup(blob, passphrase)
    assert len(data["tables"]["courses"]) == 821
    # Restore into an empty database: everything comes back, including the hidden flag.
    other = build_app()
    with other.state.session_factory() as session:
        counts = restore_data(session, data)
        session.commit()
        assert counts["courses"] == 821
        assert session.get(CourseRow, "CSC 101").hidden is True
    assert "backup.export" in _audit_actions(client)


def test_admin_uploads_may_be_larger_than_planning_requests(make_client: Callable[..., TestClient]) -> None:
    client = make_client()
    headers = {"Authorization": "Bearer test-admin-token-that-is-long-enough-123"}
    big = "code,title\n" + "CSC 999,Big course\n" * 40_000  # about 760 KB: over the 512 KB planning limit
    assert client.post("/api/v1/history/parse", json={"text": big}).status_code == 413
    response = client.post(f"{ADMIN}/courses/bulk", json={"text": big}, headers=headers)
    assert response.status_code == 422  # read, then refused for having too many rows
    assert "more than 5000 rows" in response.json()["detail"]


PASSPHRASE = "a long and private passphrase"


def test_restore_from_the_admin_page(client: TestClient, admin_headers: dict[str, str]) -> None:
    blob = client.post(f"{ADMIN}/backup", json={"passphrase": PASSPHRASE}, headers=admin_headers).content
    upload = {"backup_base64": base64.b64encode(blob).decode(), "passphrase": PASSPHRASE}
    # One change after the backup: the restore must undo it, and every API worker must notice.
    client.put(f"{ADMIN}/courses/CSC 101/hidden", json={"hidden": True}, headers=admin_headers)
    assert client.get("/api/v1/courses/CSC 101").status_code == 404

    wrong = client.post(
        f"{ADMIN}/restore/check", json={**upload, "passphrase": "not it"}, headers=admin_headers
    )
    assert wrong.status_code == 422
    assert "Wrong passphrase" in wrong.json()["detail"]
    check = client.post(f"{ADMIN}/restore/check", json=upload, headers=admin_headers).json()
    assert check["restorable"] is True
    courses = next(table for table in check["tables"] if table["name"] == "courses")
    assert courses == {"name": "courses", "in_backup": 821, "now": 821}
    assert client.get("/api/v1/courses/CSC 101").status_code == 404  # checking changes nothing

    assert (
        client.post(f"{ADMIN}/restore", json=upload, headers=admin_headers).status_code == 422
    )  # not confirmed
    done = client.post(
        f"{ADMIN}/restore", json={**upload, "confirm": "RESTORE"}, headers=admin_headers
    ).json()
    assert done["restored"]["courses"] == 821
    assert "audit_log" not in done["restored"]
    assert done["audit_log_kept"] is True
    assert client.get("/api/v1/courses/CSC 101").status_code == 200  # back as it was in the backup

    # The audit log is never rolled back: the undone change and the restore are both in it.
    assert {"backup.export", "course.hide", "backup.restore"} <= set(_audit_actions(client))
    # The data from just before the restore comes back, encrypted with the same passphrase.
    assert done["previous"]["filename"].startswith("auib-advisor-before-restore-")
    previous = read_backup(base64.b64decode(done["previous"]["data_base64"]), PASSPHRASE)
    hidden = {row["code"] for row in previous["tables"]["courses"] if row["hidden"]}
    assert hidden == {"CSC 101"}


def test_restore_refuses_a_backup_from_another_schema(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    with _session(client) as session:
        session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        session.execute(text("INSERT INTO alembic_version VALUES ('0003')"))
        session.commit()
        data = export_data(session)
    data["schema_revision"] = "0002"
    blob = encrypt(gzip.compress(json.dumps(data).encode()), PASSPHRASE)
    upload = {"backup_base64": base64.b64encode(blob).decode(), "passphrase": PASSPHRASE}
    check = client.post(f"{ADMIN}/restore/check", json=upload, headers=admin_headers).json()
    assert check["restorable"] is False
    assert "schema 0002" in check["problem"]
    confirmed = {**upload, "confirm": "RESTORE"}
    assert client.post(f"{ADMIN}/restore", json=confirmed, headers=admin_headers).status_code == 409


def test_an_upload_that_is_not_a_backup_is_refused(client: TestClient, admin_headers: dict[str, str]) -> None:
    upload = {"backup_base64": base64.b64encode(b"just a text file").decode(), "passphrase": PASSPHRASE}
    response = client.post(f"{ADMIN}/restore/check", json=upload, headers=admin_headers)
    assert response.status_code == 422
    assert "not an AUIB Academic Advisor backup" in response.json()["detail"]
