from fastapi.testclient import TestClient

CS = "casc-computer-science"


def test_health_and_ready(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    ready = client.get("/api/ready").json()
    assert ready["status"] == "ready"
    assert ready["programs"] == 3  # the CS major and two minors


def test_meta_lists_choices_and_the_disclaimer(client: TestClient) -> None:
    meta = client.get("/api/v1/meta").json()
    assert {"id": "ai", "label": "AI and machine learning"} in meta["interests"]
    assert "registrar" in meta["disclaimer"]
    assert meta["standing_credits"]["junior"] == 60


def test_programs_and_requirement_tree(client: TestClient) -> None:
    programs = client.get("/api/v1/programs?kind=major").json()
    assert [p["id"] for p in programs] == [CS]
    assert programs[0]["source_date"] == "2026-10-08"
    minors = client.get("/api/v1/programs?kind=minor").json()
    assert {(p["id"], p["name"], p["total_units"]) for p in minors} == {
        ("minor-psychology", "Psychology", 18),
        ("minor-teaching-and-learning-design", "Teaching and Learning Design", 18),
    }
    detail = client.get(f"/api/v1/programs/{CS}").json()
    assert detail["root"]["units_required"] == 126
    core = detail["root"]["children"][0]["children"][0]
    assert core["requires_all"] is True
    assert len(core["courses"]) == 20
    free = detail["root"]["children"][-1]["children"][0]
    assert free["courses"] == []  # the open pool is not listed course by course


def test_unknown_program_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/programs/nope").status_code == 404


def test_insights_list_gateways(client: TestClient) -> None:
    insights = client.get(f"/api/v1/programs/{CS}/insights").json()
    assert insights["gateways"][0]["course"]["code"] == "CSC 101"
    assert insights["longest_chain"][0]["code"] == "CSC 101"


def test_course_search_and_detail_show_rules_beside_their_source(client: TestClient) -> None:
    found = client.get("/api/v1/courses", params={"q": "machine learning"}).json()
    assert [c["code"] for c in found["courses"]] == ["CSC 333"]
    assert client.get("/api/v1/courses", params={"q": "csc231"}).json()["courses"][0]["code"] == "CSC 231"
    detail = client.get("/api/v1/courses/CSC 231").json()
    rule = detail["rules"][0]
    assert rule["rule"] == "CSC 230 AND MAT 111"
    assert rule["source_text"] == "Prerequisites: CSC 230 and MAT 111"
    assert rule["english"] == "CSC 230 and MAT 111"
    assert {"CSC 313", "CSC 343"} <= {c["code"] for c in detail["unlocks"]}
    assert client.get("/api/v1/courses/XYZ 999").status_code == 404
    assert detail["offered_terms"] is None
    assert client.get("/api/v1/courses/CSC 390").json()["offered_terms"] == ["summer"]
