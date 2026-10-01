from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from starlette.testclient import TestClient

from app.factory import create_app
from app.errors import ConfigurationError, ValidationError
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
        return_value=AuthStatusResult(
            False,
            None,
            [],
            None,
            ["https://www.googleapis.com/auth/drive"],
            "Google account is not connected",
            "Run auth_google_begin to connect a Google account.",
        ),
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
    assert payload["status_detail"] == "Google account is not connected"
    assert payload["recommended_action"] == "Run auth_google_begin to connect a Google account."


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


def test_oauth_callback_returns_safe_html_for_unexpected_failure(capsys) -> None:
    app = create_app()
    with patch(
        "app.factory.AuthService.complete_google_auth",
        side_effect=RuntimeError("provider-secret-must-not-leak"),
    ):
        with TestClient(app) as client:
            response = client.get("/oauth/google/callback?state=test-state&code=test-code")

    assert response.status_code == 500
    assert "No pudimos conectar tu cuenta" in response.text
    assert "provider-secret-must-not-leak" not in response.text
    assert "provider-secret-must-not-leak" not in capsys.readouterr().out
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "test-state" not in response.text
    assert "test-code" not in response.text


def test_callback_uses_code_and_configured_redirect_and_escapes_email() -> None:
    app = create_app()
    connection = SimpleNamespace(
        user=SimpleNamespace(external_subject="callback-user"),
        google_email='<script>alert("x")</script>@example.com',
    )
    with patch("app.factory.AuthService.complete_google_auth", return_value=connection) as complete:
        with TestClient(app) as client:
            response = client.get("/oauth/google/callback?state=state-value&code=code-value")
    complete.assert_called_once_with(state="state-value", code="code-value")
    assert response.status_code == 200
    assert "Tu cuenta de Google está conectada" in response.text
    assert "Ya puedes cerrar esta pestaña" in response.text
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text


@pytest.mark.parametrize("query", ["", "?state=only-state", "?code=only-code"])
def test_callback_missing_parameters_is_invalid(query: str) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/oauth/google/callback" + query)
    assert response.status_code == 400
    assert "El enlace ya no es válido" in response.text


def test_callback_expired_state_is_invalid() -> None:
    with patch("app.factory.AuthService.complete_google_auth", side_effect=ValidationError("expired")):
        with TestClient(create_app()) as client:
            response = client.get("/oauth/google/callback?state=expired&code=unused")
    assert response.status_code == 400
    assert "El enlace ya no es válido" in response.text


def test_callback_cancellation_consumes_state_without_exchanging_code() -> None:
    with patch("app.factory.AuthService.cancel_google_auth") as cancel, patch(
        "app.factory.AuthService.complete_google_auth"
    ) as complete:
        with TestClient(create_app()) as client:
            response = client.get("/oauth/google/callback?state=valid-state&error=access_denied")
    cancel.assert_called_once_with(state="valid-state")
    complete.assert_not_called()
    assert response.status_code == 200
    assert "Cancelaste la conexión" in response.text


def test_callback_cancellation_rejects_invalid_state() -> None:
    with patch("app.factory.AuthService.cancel_google_auth", side_effect=ValidationError("invalid")):
        with TestClient(create_app()) as client:
            response = client.get("/oauth/google/callback?state=invalid&error=access_denied")
    assert response.status_code == 400
