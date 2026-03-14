from __future__ import annotations

from unittest.mock import patch

from starlette.testclient import TestClient

from app.factory import create_app
from app.errors import ConfigurationError
from app.services.auth_service import AuthStatusResult


def test_oauth_start_requires_auth() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/oauth/google/start")

    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized_client"


def test_oauth_status_uses_authenticated_subject() -> None:
    app = create_app()
    with patch(
        "app.factory.AuthService.get_google_status",
        return_value=AuthStatusResult(False, None, [], None, ["https://www.googleapis.com/auth/drive"]),
    ):
        with TestClient(app) as client:
            response = client.get(
                "/oauth/google/status",
                headers={"Authorization": "Bearer local-dev-token"},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["connected"] is False
    assert payload["google_email"] is None
    assert payload["missing_scopes"] == ["https://www.googleapis.com/auth/drive"]


def test_oauth_start_returns_typed_app_error_payload() -> None:
    app = create_app()
    with patch(
        "app.factory.AuthService.begin_google_auth",
        side_effect=ConfigurationError("Google OAuth client credentials are not configured"),
    ):
        with TestClient(app) as client:
            response = client.get(
                "/oauth/google/start",
                headers={"Authorization": "Bearer local-dev-token"},
            )

    assert response.status_code == 500
    assert response.json() == {
        "error": "configuration_error",
        "detail": "Google OAuth client credentials are not configured",
        "retryable": False,
        "category": "internal",
    }


def test_oauth_callback_returns_internal_error_for_unexpected_failure() -> None:
    app = create_app()
    with patch("app.factory.AuthService.complete_google_auth", side_effect=RuntimeError("boom")):
        with TestClient(app) as client:
            response = client.get("/oauth/google/callback?state=test-state&code=test-code")

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"] == "internal_error"
    assert payload["detail"] == "Internal server error"
    assert payload["retryable"] is False
    assert payload["category"] == "internal"
    assert payload["metadata"] == {"endpoint": "/oauth/google/callback"}
