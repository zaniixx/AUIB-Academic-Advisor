import logging
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.importer.load import import_package
from app.importer.package import load_package
from app.security import JsonLogFormatter
from tests.conftest import PROGRAMS_DIR

CS = "casc-computer-science"
SECOND_YEAR = [
    *(
        {"code": c, "status": "completed", "term": "Fall 2025", "grade": "B"}
        for c in ["CSC 101", "MAT 111", "ENL 101", "UNI 101", "HIS 101"]
    ),
    *(
        {"code": c, "status": "completed", "term": "Spring 2026", "grade": "A-"}
        for c in ["CSC 140", "MAT 112", "ENL 201", "PSY 101", "BIO 101"]
    ),
    *(
        {"code": c, "status": "in_progress", "term": "Fall 2026"}
        for c in ["CSC 230", "CSC 132", "MAT 202", "ENL 210", "CHE 100"]
    ),
]


def test_parse_history(client: TestClient) -> None:
    paste = (
        "Course History\nCSC 101\nIntroduction to Computer Science\n2025/2026 Fall\nA\n3.00\nTaken\nTaken\n"
    )
    result = client.post("/api/v1/history/parse", json={"text": paste}).json()
    assert result["rows"][0]["code"] == "CSC 101"
    assert result["rows"][0]["status"] == "completed"
    assert result["rows"][0]["term"] == "Fall 2025"


def test_plan_for_a_new_student(client: TestClient) -> None:
    plan = client.post("/api/v1/planner/plan", json={"program_id": CS}).json()
    assert plan["start_term"]["label"] == "Spring 2027"
    assert plan["graduation_term"]["label"] == "Fall 2030"
    assert plan["on_time_term"]["label"] == "Fall 2030"
    assert len([t for t in plan["terms"] if t["term"]["season"] != "Summer"]) == 8
    summers = {i["code"] for t in plan["terms"] if t["term"]["season"] == "Summer" for i in t["items"]}
    assert summers == {"CSC 390", "CSC 391"}  # internships run in summer only
    journey = plan["degree_map"]
    assert journey["columns"][0]["label"] == "Spring 2027"
    assert {"source": "CSC 230", "target": "CSC 231"} in journey["edges"]
    swappable = [i for t in plan["terms"] for i in t["items"] if i["alternatives"]]
    assert swappable, "open choices offer replacements"
    assert plan["progress"]["percent_complete"] == 0
    assert plan["progress_with_plan"]["remaining"] == 0
    assert plan["catalog"]["source_date"] == "2026-10-08"
    assert "registrar" in plan["disclaimer"]
    slot = next(i for t in plan["terms"] for i in t["items"] if i["kind"] == "slot")
    assert slot["suggestions"], "open-choice slots come with suggestions"
    eligible = {e["course"]["code"] for e in plan["eligible_next_term"]}
    assert "CSC 101" in eligible


def test_a_student_builds_their_plan_term_by_term(client: TestClient) -> None:
    fresh = client.post("/api/v1/planner/plan", json={"program_id": CS}).json()
    assert fresh["building"]["term"]["label"] == "Spring 2027"
    assert not any(t["built"] for t in fresh["terms"])
    picks = ["CSC 101", "MAT 111", "ENL 101"]
    preferences = {
        "locks": [{"code": code, "term": "Spring 2027"} for code in picks],
        "built_terms": ["Spring 2027"],
    }
    plan = client.post("/api/v1/planner/plan", json={"program_id": CS, "preferences": preferences}).json()
    first = plan["terms"][0]
    assert first["built"] and sorted(i["code"] for i in first["items"]) == sorted(picks)
    building = plan["building"]
    assert building["term"]["label"] == plan["terms"][1]["term"]["label"]
    choices = {c["course"]["code"]: c for c in building["choices"]}
    assert "ENL 201" in choices  # its prerequisite, ENL 101, is in the built term
    later = [c for c in building["choices"] if c["planned_for"]]
    assert all(c["planned_for"]["label"] != building["term"]["label"] for c in later)

    bad = {"program_id": CS, "preferences": {"built_terms": ["Someday"]}}
    assert client.post("/api/v1/planner/plan", json=bad).status_code == 422


def test_plan_with_history_and_preferences(client: TestClient) -> None:
    body = {
        "program_id": CS,
        "attempts": SECOND_YEAR,
        "preferences": {
            "interests": ["ai"],
            "goal": "ai_engineer",
            "max_units": 18,
            "locks": [{"code": "CSC 233", "term": "Spring 2027"}],
        },
    }
    plan = client.post("/api/v1/planner/plan", json=body).json()
    assert plan["graduation_term"]["label"] == "Spring 2029"
    assert plan["progress"]["completed_units"] == 30
    assert plan["progress"]["in_progress_units"] == 15
    first = plan["terms"][0]
    assert first["term"]["label"] == "Spring 2027"
    assert any(i["code"] == "CSC 233" and i["locked"] for i in first["items"])


def test_progress_endpoint(client: TestClient) -> None:
    progress = client.post(
        "/api/v1/planner/progress", json={"program_id": CS, "attempts": SECOND_YEAR}
    ).json()
    labels = {item["group_label"] for item in progress["whats_left"]}
    assert "Major core courses" in labels
    assert "First-year experience" not in labels


def test_what_if_drop(client: TestClient) -> None:
    body = {"program_id": CS, "attempts": SECOND_YEAR, "change": {"code": "CSC 230", "action": "drop"}}
    result = client.post("/api/v1/planner/what-if", json=body).json()
    moved = {shift["code"] for shift in result["shifts"]}
    assert {"CSC 230", "CSC 231"} <= moved
    assert result["terms_later"] >= 0
    assert result["plan"]["terms"]


def test_what_if_on_an_unplanned_course_is_422(client: TestClient) -> None:
    body = {"program_id": CS, "attempts": SECOND_YEAR, "change": {"code": "CSC 101", "action": "delay"}}
    response = client.post("/api/v1/planner/what-if", json=body)
    assert response.status_code == 422
    assert "not in progress or in your plan" in response.json()["detail"]


def test_recommendations_explain_themselves(client: TestClient) -> None:
    body = {"program_id": CS, "attempts": SECOND_YEAR, "preferences": {"interests": ["ai", "culture"]}}
    groups = client.post("/api/v1/planner/recommendations", json=body).json()["groups"]
    assert groups
    for group in groups:
        for suggestion in group["suggestions"]:
            assert suggestion["reasons"]


def test_bad_input_is_rejected_without_echoing_it(client: TestClient) -> None:
    body = {"program_id": CS, "attempts": [{"code": "not a code", "status": "completed"}]}
    response = client.post("/api/v1/planner/plan", json=body)
    assert response.status_code == 422
    assert "not a code" not in response.text
    assert (
        client.post(
            "/api/v1/planner/plan", json={"program_id": CS, "preferences": {"interests": ["astrology"]}}
        ).status_code
        == 422
    )
    assert client.post("/api/v1/planner/plan", json={"program_id": CS, "surprise": 1}).status_code == 422


def test_plan_with_a_minor(client: TestClient) -> None:
    body = {"program_id": CS, "minor_id": "minor-psychology", "attempts": SECOND_YEAR}
    plan = client.post("/api/v1/planner/plan", json=body).json()
    minor = plan["minor"]
    assert minor["name"] == "Psychology"
    assert minor["source_date"] == "2024-01-14"
    after = minor["progress_with_plan"]
    assert after["completed"] + after["in_progress"] + after["planned"] >= after["units_required"] == 18
    assert minor["progress"]["not_counted"] == []
    planned = {item["code"] for term in plan["terms"] for item in term["items"] if item["code"]}
    assert (
        len(
            {"PSY 210", "PSY 226", "PSY 230", "PSY 240", "PSY 330", "PSY 332", "PSY 340", "PSY 350"} & planned
        )
        == 5
    )
    assert client.post("/api/v1/planner/plan", json={"program_id": CS}).json()["minor"] is None


def test_minor_must_be_a_published_minor(client: TestClient) -> None:
    unknown = client.post("/api/v1/planner/plan", json={"program_id": CS, "minor_id": "minor-unknown"})
    assert unknown.status_code == 404
    major = client.post("/api/v1/planner/plan", json={"program_id": CS, "minor_id": CS})
    assert major.status_code == 422


def test_recommendations_and_what_if_include_the_minor(client: TestClient) -> None:
    body = {"program_id": CS, "minor_id": "minor-teaching-and-learning-design", "attempts": SECOND_YEAR}
    groups = client.post("/api/v1/planner/recommendations", json=body).json()["groups"]
    assert "TLD minor: one 400-level course" in {group["group_label"] for group in groups}
    what_if = client.post(
        "/api/v1/planner/what-if", json={**body, "change": {"code": "CSC 230", "action": "drop"}}
    ).json()
    assert what_if["plan"]["minor"]["name"] == "Teaching and Learning Design"


def test_unknown_program(client: TestClient) -> None:
    assert client.post("/api/v1/planner/plan", json={"program_id": "nope"}).status_code == 404


def test_private_responses_are_not_cached_and_carry_security_headers(client: TestClient) -> None:
    response = client.post("/api/v1/planner/plan", json={"program_id": CS})
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]
    assert "cache-control" not in client.get("/api/v1/programs").headers


def test_logs_hold_no_course_history(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    attempts = [{"code": "CSC 101", "status": "completed", "term": "Fall 2025", "grade": "C-"}]
    client.post("/api/v1/planner/plan?ref=query-marker", json={"program_id": CS, "attempts": attempts})
    test_client_loggers = ("httpx", "httpx2", "httpcore")  # the test's own HTTP client, not the server
    records = [record for record in caplog.records if record.name.split(".")[0] not in test_client_loggers]
    lines = [JsonLogFormatter().format(record) for record in records]
    assert any('"path": "/api/v1/planner/plan"' in line for line in lines)
    assert not [line for line in lines if "CSC 101" in line or "C-" in line or "query-marker" in line]


def test_large_bodies_are_rejected(make_client: Callable[..., TestClient]) -> None:
    client = make_client(max_request_bytes=10_000)
    response = client.post("/api/v1/history/parse", json={"text": "x" * 20_000})
    assert response.status_code == 413


def test_rate_limit(make_client: Callable[..., TestClient]) -> None:
    client = make_client(rate_limit_per_minute=3)
    codes = [client.post("/api/v1/history/parse", json={"text": ""}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert client.get("/api/v1/programs").status_code == 200  # catalog reads are not limited


def test_plan_includes_gpa_and_retake_suggestions(client: TestClient) -> None:
    attempts = [
        {"code": "CSC 101", "status": "completed", "term": "Fall 2025", "grade": "A"},
        {"code": "MAT 111", "status": "completed", "term": "Fall 2025", "grade": "C-"},
        {"code": "ENL 101", "status": "completed", "term": "Spring 2026", "grade": "B+"},
        {"code": "CSC 140", "status": "completed", "term": "Spring 2026", "grade": "B"},
    ]
    gpa = client.post("/api/v1/planner/plan", json={"program_id": CS, "attempts": attempts}).json()["gpa"]
    assert gpa["cumulative"] == 3.0
    assert gpa["last_term"]["term"]["label"] == "Spring 2026"
    assert gpa["last_term"]["gpa"] == 3.15
    assert gpa["retakes"][0]["course"]["code"] == "MAT 111"
    assert gpa["retakes"][0]["with_a"] == pytest.approx(3.575, abs=0.006)  # (36.0 - 5.1 + 12) / 12
    assert gpa["assumptions"]


def test_new_students_have_no_gpa(client: TestClient) -> None:
    assert client.post("/api/v1/planner/plan", json={"program_id": CS}).json()["gpa"] is None


def test_gpa_projection_and_target(client: TestClient) -> None:
    attempts = [
        {"code": "CSC 101", "status": "completed", "term": "Fall 2025", "grade": "B"},
        {"code": "MAT 111", "status": "completed", "term": "Fall 2025", "grade": "B"},
        {"code": "CSC 230", "status": "in_progress", "term": "Fall 2026"},
        {"code": "CSC 132", "status": "in_progress", "term": "Fall 2026"},
    ]
    body = {
        "program_id": CS,
        "attempts": attempts,
        "courses": [{"code": "CSC 230", "grade": "A"}, {"code": "CSC 132"}],
        "target": 3.25,
    }
    result = client.post("/api/v1/planner/gpa", json=body).json()
    assert result["current"] == 3.0
    assert result["projected"] == pytest.approx((3 + 3 + 4) / 3, abs=0.005)  # CSC 132 has no grade yet
    assert result["courses_gpa"] == 4.0
    # 3.25 over 12 credits needs 39 points; 9 + 9 + 12 are in, so CSC 132 needs 9 / 3 = 3.0, a B.
    assert result["target"] == {
        "target": 3.25,
        "status": "reachable",
        "average_needed": 3.0,
        "grade_needed": "B",
        "open_credits": 3.0,
        "best_possible": 3.5,
    }
    out = client.post("/api/v1/planner/gpa", json={**body, "target": 3.9}).json()["target"]
    assert out["status"] == "out_of_reach"
    bad = client.post("/api/v1/planner/gpa", json={**body, "courses": [{"code": "CSC 230", "grade": "E"}]})
    assert bad.status_code == 422


def test_move_options_explain_each_term(client: TestClient) -> None:
    body = {"program_id": CS, "attempts": SECOND_YEAR, "code": "CSC 313"}
    found = client.post("/api/v1/planner/move-options", json=body).json()
    assert found["course"]["code"] == "CSC 313"
    assert found["term"]["label"] == "Fall 2027"
    by_term = {option["term"]["label"]: option for option in found["options"]}
    assert "Fall 2027" not in by_term  # where it is now
    assert by_term["Spring 2027"]["valid"] is False
    assert by_term["Spring 2027"]["problems"] == ["CSC 313 needs CSC 231 done before Spring 2027."]
    later = by_term["Spring 2029"]
    assert later["valid"] is True and later["terms_later"] == 1
    assert later["graduation_term"]["label"] == "Fall 2029"
    assert any(shift["code"] == "CSC 313" for shift in later["shifts"])


def test_move_options_refuse_a_course_already_taken(client: TestClient) -> None:
    body = {"program_id": CS, "attempts": SECOND_YEAR, "code": "CSC 101"}
    response = client.post("/api/v1/planner/move-options", json=body)
    assert response.status_code == 422
    assert "already completed" in response.json()["detail"]


def test_compare_scenarios_side_by_side(client: TestClient) -> None:
    scenarios = [
        {"name": "My plan", "program_id": CS},
        {"name": "Summers", "program_id": CS, "preferences": {"pace": "fastest", "include_summer": True}},
        {"name": "With a minor", "program_id": CS, "minor_id": "minor-psychology"},
        {"name": "Old major", "program_id": "no-such-major"},
    ]
    found = client.post(
        "/api/v1/planner/compare", json={"attempts": SECOND_YEAR, "scenarios": scenarios}
    ).json()
    mine, summers, minor, gone = found["scenarios"]
    assert mine["plan"]["semesters_vs_first"] is None
    assert mine["plan"]["graduation_term"]["label"] == "Spring 2029"
    assert summers["plan"]["semesters_vs_first"] < 0  # summers and full terms finish sooner
    assert minor["plan"]["minor_name"] == "Psychology"
    assert mine["plan"]["credits_left"] == 81
    first_term = mine["plan"]["terms"][0]
    assert first_term["units"] == sum(c["units"] for c in first_term["courses"]) + 3 * len(
        first_term["open_choices"]
    )
    assert gone["plan"] is None and "not available" in gone["error"]


def test_compare_takes_at_most_four_plans(client: TestClient) -> None:
    scenarios = [{"name": f"Plan {n}", "program_id": CS} for n in range(5)]
    response = client.post("/api/v1/planner/compare", json={"scenarios": scenarios})
    assert response.status_code == 422


def test_change_of_major_shows_which_credits_transfer(client: TestClient) -> None:
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        import_package(
            session, load_package(PROGRAMS_DIR / "casc-psychology"), actor="test", accept_warnings=True
        )
        session.commit()
    body = {"program_id": CS, "attempts": SECOND_YEAR, "target_program_id": "casc-psychology"}
    found = client.post("/api/v1/planner/change-program", json=body).json()
    assert found["current"]["name"] == "Computer Science"
    assert found["target"]["name"] == "Psychology"
    assert found["target"]["counted_credits"] < found["current"]["counted_credits"]
    courses = {course["course"]["code"]: course for course in found["courses"]}
    assert courses["CSC 230"]["state"] == "in_progress"
    assert courses["CSC 230"]["now"] == "Major core courses" and courses["CSC 230"]["after"] is None
    assert found["lost_credits"] >= 6
    assert "Psychology" in found["version_note"]
    assert any("registrar" in note for note in found["notes"])


def test_change_of_major_checks_the_programs(client: TestClient) -> None:
    body = {"program_id": CS, "attempts": SECOND_YEAR, "target_program_id": "no-such-major"}
    assert client.post("/api/v1/planner/change-program", json=body).status_code == 404
    body["target_program_id"] = "minor-psychology"
    assert client.post("/api/v1/planner/change-program", json=body).status_code == 422


def test_plan_flags_courses_that_count_twice(client: TestClient) -> None:
    body = {"program_id": CS, "attempts": SECOND_YEAR, "minor_id": "minor-psychology"}
    plan = client.post("/api/v1/planner/plan", json=body).json()
    items = [item for term in plan["terms"] for item in term["items"] if item["code"]]
    shared = [item for item in items if item["also_counts_toward"]]
    assert shared, "minor courses also count toward the major"
    assert all(item["counts_toward"] for item in items)
    assert shared[0]["also_counts_toward"] == ["Psychology minor: 5 of 8 courses"]
    groups = [plan["progress"]["root"]]
    counted = []
    while groups:
        group = groups.pop()
        counted += group["courses"]
        groups += group["children"]
    psy = next(course for course in counted if course["code"] == "PSY 101")
    assert psy["also_counts_toward"] == ["Psychology minor: PSY 101 first"]
