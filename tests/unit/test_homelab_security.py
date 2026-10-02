from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import jwt
import pytest
from fastmcp.exceptions import ToolError
from starlette.testclient import TestClient

from app.config import Settings, get_settings
from app.context.request_context import reset_request_context, set_request_context
from app.db.session import SessionLocal
from app.errors import ValidationError
from app.factory import create_app
from app.logging import redact_value
from app.main import run
from app.oauth.google_oauth import GoogleOAuthTokens
from app.security.jwt_auth import JWTAuthenticationError, build_request_context, decode_jwt
from app.services.auth_service import AuthService
from app.tools.common import run_tool


def claims(subject="jwt-user"):
    settings = get_settings()
    return {
        "sub": subject,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }


@pytest.mark.parametrize("allow_non_expiring", [False, True])
@pytest.mark.parametrize("missing", ["sub", "iss", "aud", "exp"])
def test_jwt_requires_identity_and_expiration(missing, allow_non_expiring):
    payload = claims()
    payload.pop(missing)
    settings = get_settings().model_copy(
        update={"jwt_allow_non_expiring_tokens": allow_non_expiring}
    )
    token = jwt.encode(payload, settings.jwt_shared_secret, algorithm="HS256")
    if missing == "exp" and allow_non_expiring:
        assert decode_jwt(token, settings) == payload
    else:
        with pytest.raises(JWTAuthenticationError):
            decode_jwt(token, settings)


@pytest.mark.parametrize("allow_non_expiring", [False, True])
@pytest.mark.parametrize(
    "override",
    [
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"iss": "wrong-issuer"},
        {"aud": "wrong-audience"},
    ],
)
def test_jwt_rejects_invalid_claims(override, allow_non_expiring):
    settings = get_settings().model_copy(
        update={"jwt_allow_non_expiring_tokens": allow_non_expiring}
    )
    payload = claims() | override
    token = jwt.encode(payload, settings.jwt_shared_secret, algorithm="HS256")
    with pytest.raises(JWTAuthenticationError):
        decode_jwt(token, settings)


@pytest.mark.parametrize("allow_non_expiring", [False, True])
def test_jwt_rejects_wrong_signature(allow_non_expiring):
    token = jwt.encode(claims(), "wrong-test-signing-key-at-least-32-bytes", algorithm="HS256")
    settings = get_settings().model_copy(
        update={"jwt_allow_non_expiring_tokens": allow_non_expiring}
    )
    with pytest.raises(JWTAuthenticationError):
        decode_jwt(token, settings)


def test_valid_jwt_and_multiuser_google_isolation():
    settings = get_settings()
    with SessionLocal() as session:
        service = AuthService(
            session,
            Settings(
                _env_file=None, GOOGLE_CLIENT_ID="fake-client", GOOGLE_CLIENT_SECRET="fake-secret"
            ),
        )
        one = service.begin_google_auth(external_subject="isolation-one")
        two = service.begin_google_auth(external_subject="isolation-two")
        tokens = GoogleOAuthTokens("fake-access", "fake-refresh", None, ["openid"], "fake-id")
        with (
            patch("app.services.auth_service.exchange_code", return_value=tokens),
            patch(
                "app.services.auth_service.AuthService._extract_google_identity",
                return_value=("one@example.com", "google-one"),
            ),
        ):
            service.complete_google_auth(state=one.state, code="fake-code")
        with pytest.raises(ValidationError):
            service.complete_google_auth(state=one.state, code="replay")
        service.cancel_google_auth(state=two.state)
        with pytest.raises(ValidationError):
            service.cancel_google_auth(state=two.state)

    with TestClient(create_app()) as client:
        for subject, expected in [("isolation-one", True), ("isolation-two", False)]:
            token = jwt.encode(claims(subject), settings.jwt_shared_secret, algorithm="HS256")
            response = client.get(
                "/oauth/google/status", headers={"Authorization": "Bearer " + token}
            )
            assert response.status_code == 200
            assert response.json()["connected"] is expected
            assert response.json()["google_email"] == ("one@example.com" if expected else None)


@pytest.mark.parametrize(
    "tool",
    [
        "calendar_create_event",
        "calendar_update_event",
        "calendar_confirm_delete_event",
        "gmail_create_draft",
        "gmail_update_draft",
        "gmail_delete_draft",
        "gmail_confirm_send_email",
        "gmail_delete_message",
        "tasks_create_tasklist",
        "tasks_update_tasklist",
        "tasks_create_task",
        "tasks_update_task",
        "tasks_complete_task",
        "tasks_confirm_delete_task",
        "tasks_confirm_delete_tasklist",
        "drive_create_folder",
        "drive_create_google_doc",
        "drive_create_google_sheet",
        "drive_create_google_slide",
        "drive_create_shortcut",
        "drive_update_metadata",
        "drive_move_file",
        "drive_confirm_upload",
        "drive_confirm_save_file",
        "drive_confirm_write_google_doc",
        "drive_confirm_write_google_sheet",
        "drive_confirm_delete_file",
        "drive_confirm_share_file",
        "drive_confirm_revoke_permission",
    ],
)
def test_mutations_are_blocked_before_provider_calls(tool):
    settings = Settings(_env_file=None, REQUIRE_EXPLICIT_APPROVAL=True)
    operation = Mock()
    context = build_request_context(claims())
    context_token = set_request_context(context)
    try:
        with (
            patch("app.tool_runtime.get_settings", return_value=settings),
            pytest.raises(ToolError, match="approval_required"),
        ):
            run_tool(
                tool_name=tool,
                provider="google",
                resource_type="test",
                arguments={},
                operation=operation,
            )
        operation.assert_not_called()
    finally:
        reset_request_context(context_token)


def test_sensitive_oauth_values_are_redacted_recursively():
    value = redact_value({"state": "x", "nested": [{"code": "y", "code_verifier": "z"}]})
    assert value == {
        "state": "[redacted]",
        "nested": [{"code": "[redacted]", "code_verifier": "[redacted]"}],
    }


def test_uvicorn_does_not_log_callback_queries():
    with patch("app.main.uvicorn.run") as start:
        run()
    assert start.call_args.kwargs["access_log"] is False


@pytest.mark.parametrize("allow_non_expiring", [False, True])
def test_local_credential_utility_preserves_keys_and_writes_token(tmp_path, allow_non_expiring):
    import subprocess
    import sys
    from pathlib import Path

    from dotenv import dotenv_values

    env_file = tmp_path / ".env"
    env_file.write_text(
        "TOKEN_ENCRYPTION_KEY=\nJWT_SHARED_SECRET=\nJWT_TEST_MODE=false\nJWT_ALGORITHMS=HS256\nJWT_ISSUER=urn:test:homelab\nJWT_AUDIENCE=google-mcp-server\n"
    )
    with env_file.open("a") as env:
        env.write(f"JWT_ALLOW_NON_EXPIRING_TOKENS={str(allow_non_expiring).lower()}\n")
    project_root = Path(__file__).resolve().parents[2]
    command = [sys.executable, "-m", "scripts.homelab_credentials", "--env", str(env_file)]
    subprocess.run(command + ["init"], cwd=project_root, check=True, capture_output=True)
    first = dotenv_values(env_file)
    subprocess.run(command + ["init"], cwd=project_root, check=True, capture_output=True)
    assert dotenv_values(env_file) == first
    assert env_file.stat().st_mode & 0o777 == 0o600
    output = tmp_path / "user.token"
    result = subprocess.run(
        command + ["issue-token", "--subject", "known-user", "--output", str(output)],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    token = output.read_text().strip()
    assert token not in result.stdout
    assert output.stat().st_mode & 0o777 == 0o600
    payload = jwt.decode(
        token,
        first["JWT_SHARED_SECRET"],
        algorithms=["HS256"],
        issuer="urn:test:homelab",
        audience="google-mcp-server",
    )
    assert payload["sub"] == "known-user"
    settings = Settings(
        _env_file=None,
        JWT_SHARED_SECRET=first["JWT_SHARED_SECRET"],
        JWT_ISSUER="urn:test:homelab",
        JWT_AUDIENCE="google-mcp-server",
        JWT_ALLOW_NON_EXPIRING_TOKENS=allow_non_expiring,
    )
    assert decode_jwt(token, settings) == payload
    assert "iat" in payload
    if allow_non_expiring:
        assert "exp" not in payload
        with pytest.raises(JWTAuthenticationError):
            decode_jwt(token, settings.model_copy(update={"jwt_allow_non_expiring_tokens": False}))
    else:
        assert payload["exp"] - payload["iat"] == 3600
    assert "approved_tools" not in payload
