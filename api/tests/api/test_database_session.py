"""A change is saved before its response is sent, so the browser's next request sees it."""

from collections.abc import Awaitable, Callable, MutableMapping
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from tests.api.conftest import ADMIN_TOKEN

Message = MutableMapping[str, Any]


def test_a_change_is_committed_before_the_response_is_sent(
    make_client: Callable[..., TestClient], tmp_path: Path
) -> None:
    database = f"sqlite+pysqlite:///{(tmp_path / 'advisor.sqlite3').as_posix()}"
    app = make_client(database_url=database).app
    other_connection = create_engine(database)  # sees only what has been committed
    saved_when_sent: list[int] = []

    async def watched(
        scope: Message, receive: Callable[[], Awaitable[Message]], send: Callable[[Message], Awaitable[None]]
    ) -> None:
        async def spy(message: Message) -> None:
            if message["type"] == "http.response.start" and scope.get("method") == "PUT":
                with other_connection.connect() as connection:
                    saved_when_sent.append(
                        connection.execute(text("SELECT count(*) FROM staff")).scalar_one()
                    )
            await send(message)

        await app(scope, receive, spy)

    response = TestClient(watched).put(
        "/api/v1/admin/staff",
        json={"email": "advisor@auib.edu.iq", "role": "advisor"},
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    )
    assert response.status_code == 200
    assert saved_when_sent == [1]
    other_connection.dispose()
