from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import jwt
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from sqlalchemy import select
from starlette.testclient import TestClient

from app.config import get_settings
from app.context.request_context import reset_request_context, set_request_context
from app.db.models import AuditLog, User
from app.db.repositories.users import UserRepository
from app.db.session import SessionLocal
from app.errors import PermissionDeniedError
from app.factory import create_app
from app.mcp_server import mcp
from app.security.authorization import authorize_tool, permissions
from app.security.jwt_auth import build_request_context
from app.security.tool_policy import PREPARE_TOOLS, TOOL_POLICIES, WRITE_TOOLS
from app.services.auth_service import AuthService
from app.tools.common import run_tool
from scripts.homelab_credentials import main


@pytest.fixture
def policy_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "authorization_mode", "server_policy")
    monkeypatch.setattr(settings, "require_explicit_approval", True)
    return settings


def set_profile(subject, profile, tenant_id=None):
    with SessionLocal() as session:
        user = UserRepository(session).get_or_create(subject, tenant_id)
        user.access_profile = profile
        session.commit()


def invoke(subject, tool_name, operation, *, tenant_id=None, claims=None):
    context = build_request_context(
        {
            "sub": subject,
            "tenant_id": tenant_id or "test-tenant",
            "iss": "test",
            "aud": "test",
            **(claims or {}),
        }
    )
    token = set_request_context(context)
    try:
        return run_tool(
            tool_name=tool_name,
            provider="google",
            resource_type="test",
            arguments={},
            operation=operation,
        )
    finally:
        reset_request_context(token)


@pytest.mark.parametrize("tool_name", sorted(WRITE_TOOLS | PREPARE_TOOLS))
def test_persistent_policy_controls_every_mutation(policy_settings, tool_name):
    subject = uuid4().hex
    operation = Mock(return_value={"ok": True})
    with pytest.raises(ToolError, match="permission_denied"):
        invoke(subject, tool_name, operation, claims={"approved_tools": [tool_name]})
    operation.assert_not_called()
    set_profile(subject, "read_write", "test-tenant")
    assert invoke(subject, tool_name, operation) == {"ok": True}
    operation.assert_called_once()
    set_profile(subject, "read_only", "test-tenant")
    with pytest.raises(ToolError, match="permission_denied"):
        invoke(subject, tool_name, operation)
    assert operation.call_count == 1


def test_tenant_isolation_unknown_tools_and_denial_audit(policy_settings):
    subject = uuid4().hex
    set_profile(subject, "read_write", "tenant-a")
    with pytest.raises(ToolError, match="permission_denied"):
        invoke(subject, "tasks_create_task", Mock(), tenant_id="tenant-b")
    with pytest.raises(ToolError, match="permission_denied"):
        invoke(subject, "unclassified_action", Mock(), tenant_id="tenant-a")
    with SessionLocal() as session:
        logs = session.scalars(
            select(AuditLog)
            .join(User)
            .where(User.external_subject == subject, AuditLog.error_code == "permission_denied")
        ).all()
        assert len(logs) == 2


def bearer(settings, subject):
    return jwt.encode(
        {
            "sub": subject,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_shared_secret,
        algorithm="HS256",
    )


def rpc(client, headers, method, params, identifier=1):
    response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": identifier,
            "method": method,
            "params": params,
        },
    )
    assert response.status_code == 200, response.text
    if response.headers.get("mcp-session-id"):
        headers["mcp-session-id"] = response.headers["mcp-session-id"]
    if "text/event-stream" in response.headers.get("content-type", ""):
        body = json.loads(
            next(line[6:] for line in response.text.splitlines() if line.startswith("data: "))
        )
    else:
        body = response.json()
    assert "error" not in body, body
    return body["result"]


def tool_call(client, headers, name, args):
    result = rpc(client, headers, "tools/call", {"name": name, "arguments": args})
    return result, json.loads(result["content"][0]["text"])


def test_one_jwt_creates_edits_deletes_and_live_revocation(policy_settings):
    subject = uuid4().hex
    set_profile(subject, "read_write")
    token = bearer(policy_settings, subject)
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
    with (
        patch(
            "app.google.tasks_client.TasksClient.create_task",
            return_value={"id": "task-1", "title": "test", "status": "needsAction"},
        ) as create,
        patch(
            "app.google.tasks_client.TasksClient.update_task",
            return_value={"id": "task-1", "title": "edited", "status": "needsAction"},
        ) as edit,
        patch(
            "app.google.tasks_client.TasksClient.get_task",
            return_value={"id": "task-1", "title": "edited", "status": "needsAction"},
        ),
        patch("app.google.tasks_client.TasksClient.delete_task") as delete,
        TestClient(create_app()) as client,
    ):
        rpc(
            client,
            headers,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "persistent-policy-test", "version": "1"},
            },
        )
        _, access = tool_call(client, headers, "auth_get_permissions", {})
        assert access["access_profile"] == "read_write"
        assert access["authorization_mode"] == "server_policy"
        _, task = tool_call(
            client,
            headers,
            "tasks_create_task",
            {"tasklist_id": "list-1", "task": {"title": "test"}},
        )
        assert task["id"] == "task-1"
        _, edited = tool_call(
            client,
            headers,
            "tasks_update_task",
            {"tasklist_id": "list-1", "task_id": "task-1", "task": {"title": "edited"}},
        )
        assert edited["title"] == "edited"
        _, preview = tool_call(
            client, headers, "tasks_delete_task", {"tasklist_id": "list-1", "task_id": "task-1"}
        )
        assert preview["requires_confirmation"] is True
        assert preview["confirmation_tool"] == "tasks_confirm_delete_task"
        set_profile(subject, "read_only")
        result, error = tool_call(
            client, headers, preview["confirmation_tool"], preview["confirmation_arguments"]
        )
        assert result["isError"] is True
        assert error["error"] == "permission_denied"
        delete.assert_not_called()
        set_profile(subject, "read_write")
        _, deleted = tool_call(
            client, headers, preview["confirmation_tool"], preview["confirmation_arguments"]
        )
        assert deleted["deleted"] is True
        replay, error = tool_call(
            client, headers, preview["confirmation_tool"], preview["confirmation_arguments"]
        )
        assert replay["isError"] is True
        assert "consumed" in error["error"]
        assert headers["Authorization"] == "Bearer " + token
        create.assert_called_once()
        edit.assert_called_once()
        delete.assert_called_once()
        set_profile(subject, "disabled")
        denied = client.get("/oauth/google/status", headers=headers)
        assert denied.status_code == 403
        assert denied.json()["error"] == "permission_denied"
        assert client.post("/mcp", headers=headers, json={}).status_code == 403


def test_disabled_identity_cannot_complete_pending_oauth(policy_settings):
    subject = uuid4().hex
    with SessionLocal() as session:
        service = AuthService(session)
        started = service.begin_google_auth(external_subject=subject)
    set_profile(subject, "disabled")
    with SessionLocal() as session, patch("app.services.auth_service.exchange_code") as exchange:
        with pytest.raises(PermissionDeniedError):
            AuthService(session).complete_google_auth(state=started.state, code="fake-code")
        exchange.assert_not_called()
    # OAuth states are single-use, including rejected callbacks. Prepare a fresh state.
    set_profile(subject, "read_only")
    with SessionLocal() as session:
        started = AuthService(session).begin_google_auth(external_subject=subject)
    set_profile(subject, "disabled")
    with (
        TestClient(create_app()) as client,
        patch("app.services.auth_service.exchange_code") as exchange,
    ):
        result = client.get(
            "/oauth/google/callback", params={"state": started.state, "code": "fake"}
        )
        assert result.status_code == 403
        exchange.assert_not_called()


def test_http_disconnect_is_authorized_and_audited(policy_settings):
    subject = uuid4().hex
    headers = {"Authorization": "Bearer " + bearer(policy_settings, subject)}
    with (
        TestClient(create_app()) as client,
        patch(
            "app.services.auth_service.AuthService.disconnect_google", return_value=True
        ) as disconnect,
    ):
        denied = client.post("/oauth/google/disconnect", headers=headers)
        assert denied.status_code == 403
        disconnect.assert_not_called()
        set_profile(subject, "read_write")
        assert client.post("/oauth/google/disconnect", headers=headers).status_code == 200
        disconnect.assert_called_once()


def test_admin_provisions_and_audits_without_signing_secret(tmp_path, monkeypatch):
    subject = uuid4().hex
    env = tmp_path / "empty.env"
    env.touch()
    monkeypatch.setenv("JWT_SHARED_SECRET", "")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "access",
            "--env",
            str(env),
            "set-access",
            "--subject",
            subject,
            "--tenant-id",
            "tenant-admin",
            "--profile",
            "read_write",
        ],
    )
    main()
    with SessionLocal() as session:
        user = UserRepository(session).get_by_external_subject(subject, "tenant-admin")
        assert user.access_profile == "read_write"
        audit = session.scalar(select(AuditLog).where(AuditLog.user_id == user.id))
        assert audit.arguments_redacted == {
            "previous_profile": "read_only",
            "access_profile": "read_write",
        }
    monkeypatch.setattr(
        sys, "argv", ["access", "--env", str(env), "get-access", "--subject", uuid4().hex]
    )
    main()


@pytest.mark.asyncio
async def test_all_registered_tools_have_catalog_and_annotations():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    assert {tool.name for tool in tools} == set(TOOL_POLICIES)
    for tool in tools:
        assert tool.annotations.read_only_hint == (TOOL_POLICIES[tool.name].kind == "read")
        if tool.name in PREPARE_TOOLS:
            assert tool.annotations.destructive_hint is False
            assert tool.annotations.idempotent_hint is False


def test_production_policy_no_longer_requires_claims(policy_settings):
    settings = policy_settings.model_copy(
        update={
            "app_env": "production",
            "jwt_test_mode": False,
            "app_base_url": "https://mcp.example.com",
            "google_redirect_uri": "https://mcp.example.com/cb",
            "allowed_hosts": "mcp.example.com",
            "require_explicit_approval": False,
            "approval_required_tools": "",
        }
    )
    settings.validate_startup()
    settings.authorization_mode = "jwt_claims"
    with pytest.raises(ValueError, match="approval for every write"):
        settings.validate_startup()


def test_permissions_refresh_even_in_same_session(policy_settings):
    subject = uuid4().hex
    set_profile(subject, "read_write")
    with SessionLocal() as session:
        kwargs = {
            "settings": policy_settings,
            "subject": subject,
            "tenant_id": None,
            "approved_tools": (),
        }
        assert "tasks_create_task" in permissions(session, **kwargs)["allowed_tools"]
        set_profile(subject, "read_only")
        assert "tasks_create_task" not in permissions(session, **kwargs)["allowed_tools"]
        with pytest.raises(PermissionDeniedError):
            authorize_tool(session, tool_name="tasks_create_task", **kwargs)
