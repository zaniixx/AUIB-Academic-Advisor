"""Who may use which endpoint, checked on every route the app has, so a new endpoint cannot forget it.

Course and program data need a signed-in AUIB student (F9.1, ADR 0007); the admin API needs a signed-in
admin or the master token (ADR 0009); health checks and sign-in stay open.
"""

import re
from collections.abc import Callable

from fastapi.testclient import TestClient

OPEN = {"/api/health", "/api/ready"}
OPEN_PREFIXES = ("/api/v1/auth/",)
ADMIN_PREFIX = "/api/v1/admin"


def _routes(client: TestClient) -> list[tuple[str, str]]:
    """Every (method, path) of the API, from its OpenAPI schema, with path parameters filled in."""
    paths = client.app.openapi()["paths"]  # type: ignore[attr-defined]
    return [
        (method.upper(), re.sub(r"\{[^}]+\}", "1", path))
        for path, methods in paths.items()
        for method in methods
    ]


def test_every_route_is_open_for_students_or_for_admins(
    client: TestClient, anonymous_client: TestClient
) -> None:
    routes = _routes(client)
    student_routes = [
        (m, p) for m, p in routes if p not in OPEN and not p.startswith((*OPEN_PREFIXES, ADMIN_PREFIX))
    ]
    admin_routes = [(m, p) for m, p in routes if p.startswith(ADMIN_PREFIX)]
    assert len(student_routes) > 10 and len(admin_routes) > 20  # the route table was read

    for method, path in student_routes:
        response = anonymous_client.request(method, path, json={})
        assert response.status_code == 401, (method, path)
        assert response.json() == {"detail": "Sign in with your AUIB email address to continue."}

    for method, path in admin_routes:
        assert anonymous_client.request(method, path, json={}).status_code == 401, (method, path)
        student = client.request(method, path, json={})  # signed in, but not an admin
        assert student.status_code == 403, (method, path)
        assert "not an admin" in student.json()["detail"]
        wrong = client.request(method, path, json={}, headers={"Authorization": "Bearer wrong"})
        assert wrong.status_code == 401, (method, path)

    assert anonymous_client.get("/api/health").status_code == 200
    assert anonymous_client.get("/api/ready").status_code == 200
    assert anonymous_client.get("/api/v1/auth/me").status_code == 401  # open route, but no one signed in


def test_without_a_master_token_only_signed_in_admins_get_in(make_client: Callable[..., TestClient]) -> None:
    client = make_client(admin_token=None)
    bearer = client.get(f"{ADMIN_PREFIX}/rules", headers={"Authorization": "Bearer anything"})
    assert bearer.status_code == 503
    assert client.get(f"{ADMIN_PREFIX}/rules").status_code == 403  # the student's own sign-in
