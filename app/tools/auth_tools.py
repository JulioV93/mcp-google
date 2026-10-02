from __future__ import annotations

from fastmcp import FastMCP

from app.config import Settings
from app.services.auth_service import AuthService
from app.tools.common import run_tool


def register_auth_tools(mcp: FastMCP, *, settings: Settings) -> None:
    @mcp.tool
    def auth_google_begin() -> dict[str, object]:
        """Start the Google OAuth connection flow for the current user."""
        return run_tool(
            tool_name="auth_google_begin",
            provider="google",
            resource_type="oauth",
            arguments={},
            operation=lambda session, context: _auth_google_begin(session, context, settings),
        )

    @mcp.tool
    def auth_google_status() -> dict[str, object]:
        """Return the Google connection status for the current user."""
        return run_tool(
            tool_name="auth_google_status",
            provider="google",
            resource_type="oauth",
            arguments={},
            operation=lambda session, context: _auth_google_status(session, context, settings),
        )

    @mcp.tool
    def auth_google_disconnect() -> dict[str, object]:
        """Disconnect the current user's Google account."""
        return run_tool(
            tool_name="auth_google_disconnect",
            provider="google",
            resource_type="oauth",
            arguments={},
            operation=lambda session, context: _auth_google_disconnect(session, context, settings),
        )


def _auth_google_begin(session, context, settings: Settings) -> dict[str, object]:
    service = AuthService(session, settings)
    result = service.begin_google_auth(
        external_subject=context.subject,
        tenant_id=context.tenant_id,
    )
    return {
        "authorization_url": result.authorization_url,
        "state": result.state,
        "expires_at": result.expires_at,
        "scopes": result.scopes,
    }


def _auth_google_status(session, context, settings: Settings) -> dict[str, object]:
    service = AuthService(session, settings)
    result = service.get_google_status(
        external_subject=context.subject,
        tenant_id=context.tenant_id,
    )
    return {
        "connected": result.connected,
        "google_email": result.google_email,
        "scopes": result.scopes,
        "status": result.status,
        "missing_scopes": result.missing_scopes,
        "status_detail": result.status_detail,
        "recommended_action": result.recommended_action,
    }


def _auth_google_disconnect(session, context, settings: Settings) -> dict[str, object]:
    service = AuthService(session, settings)
    disconnected = service.disconnect_google(
        external_subject=context.subject,
        tenant_id=context.tenant_id,
    )
    return {"disconnected": disconnected}
