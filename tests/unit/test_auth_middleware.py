from starlette.testclient import TestClient

from app.config import Settings
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


def test_allowed_host_list_defaults_to_local_hosts_in_development() -> None:
    settings = Settings.model_validate({"APP_ENV": "development"})

    assert settings.allowed_host_list == ["localhost", "127.0.0.1", "testserver"]


def test_allowed_host_list_uses_app_base_url_in_production() -> None:
    settings = Settings.model_validate(
        {
            "APP_ENV": "production",
            "APP_BASE_URL": "https://mcp.example.com",
        }
    )

    assert settings.allowed_host_list == ["mcp.example.com"]
