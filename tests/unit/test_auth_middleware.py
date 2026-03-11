from starlette.testclient import TestClient

from app.factory import create_app


def test_healthcheck_is_public() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["authenticated_subject"] is None


def test_mcp_requires_bearer_token() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/mcp")

    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized_client"


def test_mcp_accepts_dev_bearer_token() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get(
            "/mcp",
            headers={
                "Authorization": "Bearer local-dev-token",
                "Accept": "text/event-stream",
            },
        )

    assert response.status_code in {200, 202, 400, 406}
    assert response.status_code != 401
