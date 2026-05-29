from fastapi.testclient import TestClient

from main import app


def test_health_and_roles() -> None:
    with TestClient(app) as client:
        homepage = client.get("/")
        assert homepage.status_code == 200
        assert "RAG" in homepage.text

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        roles = client.get("/roles")
        assert roles.status_code == 200
        payload = roles.json()
        assert len(payload) >= 4
        assert any(item["role_id"] == "virtual_friend" for item in payload)


def test_create_user() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/users",
            json={"name": "测试用户", "profile": {"city": "上海"}},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["name"] == "测试用户"
        assert payload["profile"]["city"] == "上海"


def test_chat_stream_endpoint_returns_ndjson() -> None:
    class _ChatService:
        def stream_chat(self, payload):  # noqa: ANN001
            assert payload.message == "hello"
            yield {"type": "chunk", "content": "live "}
            yield {
                "type": "done",
                "answer": "live answer",
                "references": [],
                "memory_size": 2,
                "session_id": payload.session_id,
                "role_id": payload.role_id,
            }

    with TestClient(app) as client:
        original = client.app.state.services["chat_service"]
        client.app.state.services["chat_service"] = _ChatService()
        try:
            with client.stream(
                "POST",
                "/chat/stream",
                json={
                    "session_id": "session-1",
                    "user_id": "user-1",
                    "role_id": "virtual_friend",
                    "message": "hello",
                },
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("application/x-ndjson")
                lines = [line for line in response.iter_lines() if line]
        finally:
            client.app.state.services["chat_service"] = original

    assert len(lines) == 2
    assert '"type": "chunk"' in lines[0]
    assert '"type": "done"' in lines[1]
