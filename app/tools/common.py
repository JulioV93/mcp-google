from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from app.context.request_context import maybe_get_request_context
from app.errors import AppError, UnauthorizedError
from app.tool_runtime import audited_call, ensure_tool_approval


def register_ping_tool(mcp: FastMCP, *, server_name: str, server_version: str) -> None:
    @mcp.tool
    def ping() -> dict[str, str]:
        """Return the current server status."""
        context = maybe_get_request_context()
        return {
            "status": "ok",
            "server": server_name,
            "version": server_version,
            "subject": context.subject if context else "anonymous",
            "token_type": context.token_type if context else "none",
        }


def require_context():
    context = maybe_get_request_context()
    if context is None:
        raise UnauthorizedError("Authenticated request context is required")
    return context


def run_tool(
    *,
    tool_name: str,
    provider: str,
    resource_type: str,
    arguments: dict[str, object],
    operation: Callable[[Any, Any], dict[str, object]],
) -> dict[str, object]:
    context = require_context()
    ensure_tool_approval(tool_name=tool_name, approved_tools=context.approvals)
    try:
        return audited_call(
            external_subject=context.subject,
            tenant_id=context.tenant_id,
            tool_name=tool_name,
            provider=provider,
            resource_type=resource_type,
            arguments=arguments,
            operation=lambda session: operation(session, context),
        )
    except AppError as exc:
        raise exc.to_tool_error() from exc
