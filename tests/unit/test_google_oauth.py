from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.config import Settings
from app.oauth.google_oauth import GOOGLE_AUTH_URI, allow_insecure_transport_for_local_dev, exchange_code


def test_google_auth_uri_uses_v2_endpoint() -> None:
    assert GOOGLE_AUTH_URI == "https://accounts.google.com/o/oauth2/v2/auth"


def test_exchange_code_prefers_authorization_response_and_includes_client_id() -> None:
    credentials = SimpleNamespace(
        token="access-token",
        refresh_token="refresh-token",
        expiry=None,
        scopes=["openid"],
        id_token="id-token",
    )
    flow = Mock()
    flow.credentials = credentials

    with patch("app.oauth.google_oauth.create_flow", return_value=flow):
        result = exchange_code(
            state="state-1",
            code="code-1",
            code_verifier="verifier-1",
            authorization_response="http://localhost:8000/oauth/google/callback?code=abc&state=xyz",
        )

    flow.fetch_token.assert_called_once_with(
        authorization_response="http://localhost:8000/oauth/google/callback?code=abc&state=xyz",
        include_client_id=True,
    )
    assert result.access_token == "access-token"
    assert result.refresh_token == "refresh-token"


def test_local_dev_http_oauth_temporarily_allows_insecure_transport() -> None:
    settings = Settings.model_validate(
        {
            "APP_ENV": "development",
            "GOOGLE_REDIRECT_URI": "http://localhost:8000/oauth/google/callback",
            "GOOGLE_CLIENT_ID": "client-id",
            "GOOGLE_CLIENT_SECRET": "client-secret",
        }
    )
    os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)

    with allow_insecure_transport_for_local_dev(settings):
        assert os.environ.get("OAUTHLIB_INSECURE_TRANSPORT") == "1"

    assert "OAUTHLIB_INSECURE_TRANSPORT" not in os.environ


def test_non_local_oauth_does_not_allow_insecure_transport() -> None:
    settings = Settings.model_validate(
        {
            "APP_ENV": "production",
            "GOOGLE_REDIRECT_URI": "https://example.com/oauth/google/callback",
            "GOOGLE_CLIENT_ID": "client-id",
            "GOOGLE_CLIENT_SECRET": "client-secret",
        }
    )
    os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)

    with allow_insecure_transport_for_local_dev(settings):
        assert os.environ.get("OAUTHLIB_INSECURE_TRANSPORT") is None


def test_default_settings_use_google_userinfo_scopes() -> None:
    settings = Settings.model_construct(
        app_env="development",
        app_host="0.0.0.0",
        app_port=8000,
        app_base_url="http://localhost:8000",
        database_url="sqlite:///./data/dev.db",
        allowed_origins="http://localhost:8000,http://127.0.0.1:8000",
        rate_limit_enabled=True,
        rate_limit_rpm=120,
        log_level="INFO",
        log_json=False,
        require_explicit_approval=False,
        approval_required_tools=(
            "gmail_send_email,"
            "gmail_delete_message,"
            "calendar_delete_event,"
            "calendar_confirm_delete_event,"
            "tasks_delete_task,"
            "tasks_delete_tasklist,"
            "tasks_confirm_delete_task,"
            "tasks_confirm_delete_tasklist,"
            "drive_confirm_upload,"
            "drive_confirm_save_file,"
            "drive_confirm_delete_file,"
            "drive_confirm_share_file,"
            "drive_confirm_revoke_permission"
        ),
        token_encryption_key="",
        mcp_server_name="google-mcp-server",
        mcp_server_version="0.1.0",
        mcp_path="/mcp",
        google_client_id="client-id",
        google_client_secret="client-secret",
        google_redirect_uri="http://localhost:8000/oauth/google/callback",
        google_id_token_clock_skew_seconds=10,
        google_oauth_scopes=(
            "https://www.googleapis.com/auth/calendar,"
            "https://www.googleapis.com/auth/tasks,"
            "https://www.googleapis.com/auth/gmail.readonly,"
            "https://www.googleapis.com/auth/gmail.compose,"
            "https://www.googleapis.com/auth/gmail.modify,"
            "https://www.googleapis.com/auth/drive,"
            "openid,https://www.googleapis.com/auth/userinfo.email,"
            "https://www.googleapis.com/auth/userinfo.profile"
        ),
        drive_inline_content_limit_bytes=262144,
        drive_confirmation_ttl_seconds=600,
        jwt_issuer="http://localhost:8000/auth/dev",
        jwt_audience="google-mcp-server",
        jwt_algorithms="HS256,RS256",
        jwt_jwks_url=None,
        jwt_public_key=None,
        jwt_shared_secret=None,
        jwt_test_mode=True,
        jwt_test_token="local-dev-token",
        jwt_test_subject="local-dev-user",
    )

    assert "openid" in settings.google_oauth_scope_list
    assert "https://www.googleapis.com/auth/userinfo.email" in settings.google_oauth_scope_list
    assert "https://www.googleapis.com/auth/userinfo.profile" in settings.google_oauth_scope_list
    assert "https://www.googleapis.com/auth/drive" in settings.google_oauth_scope_list
    assert "email" not in settings.google_oauth_scope_list
    assert "profile" not in settings.google_oauth_scope_list
