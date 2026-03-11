from __future__ import annotations

from starlette.testclient import TestClient

from app.factory import create_app


def test_oauth_start_requires_auth() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/oauth/google/start")

    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized_client"


def test_oauth_status_uses_authenticated_subject() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get(
            "/oauth/google/status",
            headers={"Authorization": "Bearer local-dev-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["connected"] is False
    assert payload["google_email"] is None
