from __future__ import annotations

from fastmcp import FastMCP

from app.schemas.gmail import (
    GmailCreateDraftInput,
    GmailDeleteDraftInput,
    GmailDeleteMessageInput,
    GmailGetMessageInput,
    GmailListMessagesInput,
    GmailListThreadsInput,
    GmailSendEmailInput,
    GmailUpdateDraftInput,
)
from app.services.gmail_service import GmailService
from app.tools.common import run_tool


def register_gmail_tools(mcp: FastMCP) -> None:
    @mcp.tool
    def gmail_list_messages(
        query: str | None = None,
        max_results: int = 20,
        page_token: str | None = None,
    ) -> dict[str, object]:
        """List Gmail messages for the current user."""
        payload = GmailListMessagesInput(query=query, max_results=max_results, page_token=page_token)
        return run_tool(
            tool_name="gmail_list_messages",
            provider="google",
            resource_type="gmail_message",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: GmailService(session).list_messages(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def gmail_get_message(message_id: str) -> dict[str, object]:
        """Get a Gmail message by ID."""
        payload = GmailGetMessageInput(message_id=message_id)
        return run_tool(
            tool_name="gmail_get_message",
            provider="google",
            resource_type="gmail_message",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: GmailService(session).get_message(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def gmail_list_threads(
        query: str | None = None,
        max_results: int = 20,
        page_token: str | None = None,
    ) -> dict[str, object]:
        """List Gmail threads for the current user."""
        payload = GmailListThreadsInput(query=query, max_results=max_results, page_token=page_token)
        return run_tool(
            tool_name="gmail_list_threads",
            provider="google",
            resource_type="gmail_thread",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: GmailService(session).list_threads(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def gmail_create_draft(message: dict[str, object] | None = None) -> dict[str, object]:
        """Create a Gmail draft."""
        payload = GmailCreateDraftInput.model_validate({"message": message or {}})
        return run_tool(
            tool_name="gmail_create_draft",
            provider="google",
            resource_type="gmail_draft",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: GmailService(session).create_draft(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def gmail_update_draft(draft_id: str, message: dict[str, object] | None = None) -> dict[str, object]:
        """Update a Gmail draft."""
        payload = GmailUpdateDraftInput.model_validate({"draft_id": draft_id, "message": message or {}})
        return run_tool(
            tool_name="gmail_update_draft",
            provider="google",
            resource_type="gmail_draft",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: GmailService(session).update_draft(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def gmail_delete_draft(draft_id: str) -> dict[str, object]:
        """Delete a Gmail draft."""
        payload = GmailDeleteDraftInput(draft_id=draft_id)
        return run_tool(
            tool_name="gmail_delete_draft",
            provider="google",
            resource_type="gmail_draft",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: GmailService(session).delete_draft(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def gmail_send_email(message: dict[str, object] | None = None) -> dict[str, object]:
        """Send an email through Gmail."""
        payload = GmailSendEmailInput.model_validate({"message": message or {}})
        return run_tool(
            tool_name="gmail_send_email",
            provider="google",
            resource_type="gmail_message",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: GmailService(session).send_email(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def gmail_delete_message(message_id: str) -> dict[str, object]:
        """Delete a Gmail message."""
        payload = GmailDeleteMessageInput(message_id=message_id)
        return run_tool(
            tool_name="gmail_delete_message",
            provider="google",
            resource_type="gmail_message",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: GmailService(session).delete_message(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )
