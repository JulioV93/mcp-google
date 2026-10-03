from __future__ import annotations

from fastmcp import FastMCP

from app.schemas.gmail import (
    GmailConfirmSendEmailInput,
    GmailCreateDraftInput,
    GmailDeleteDraftInput,
    GmailDeleteMessageInput,
    GmailGetMessageInput,
    GmailListMessagesInput,
    GmailListThreadsInput,
    GmailSendEmailInput,
    GmailUpdateDraftInput,
)
from app.security.tool_policy import tool_annotations
from app.services.gmail_service import GmailService
from app.tools.common import run_tool


def register_gmail_tools(mcp: FastMCP) -> None:
    @mcp.tool(annotations=tool_annotations("gmail_list_messages"))
    def gmail_list_messages(
        query: str | None = None,
        max_results: int = 20,
        page_token: str | None = None,
    ) -> dict[str, object]:
        """List Gmail messages for the current user.

        Use to search for candidate message IDs before reading or mutating a specific message.

        Example payload:
        ```json
        {
          "query": "from:person@example.com newer_than:7d",
          "max_results": 10
        }
        ```
        """
        payload = GmailListMessagesInput(
            query=query, max_results=max_results, page_token=page_token
        )
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

    @mcp.tool(annotations=tool_annotations("gmail_get_message"))
    def gmail_get_message(message_id: str) -> dict[str, object]:
        """Get a Gmail message by ID.

        Use only after you already know the message ID from a list or search step.
        """
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

    @mcp.tool(annotations=tool_annotations("gmail_list_threads"))
    def gmail_list_threads(
        query: str | None = None,
        max_results: int = 20,
        page_token: str | None = None,
    ) -> dict[str, object]:
        """List Gmail threads for the current user.

        Prefer this over listing messages when the user cares about conversation context.
        """
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

    @mcp.tool(annotations=tool_annotations("gmail_create_draft"))
    def gmail_create_draft(message: dict[str, object] | None = None) -> dict[str, object]:
        """Create a Gmail draft.

        Use when the user wants to review, edit, or approve the email before it is sent.
        Prefer this when send intent is ambiguous.

        Example payload:
        ```json
        {
          "message": {
            "to": ["person@example.com"],
            "subject": "Seguimiento",
            "body_text": "Te comparto el resumen del dia."
          }
        }
        ```
        """
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

    @mcp.tool(annotations=tool_annotations("gmail_update_draft"))
    def gmail_update_draft(
        draft_id: str, message: dict[str, object] | None = None
    ) -> dict[str, object]:
        """Update a Gmail draft.

        Use to revise an existing draft by ID before sending.
        """
        payload = GmailUpdateDraftInput.model_validate(
            {"draft_id": draft_id, "message": message or {}}
        )
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

    @mcp.tool(annotations=tool_annotations("gmail_delete_draft"))
    def gmail_delete_draft(draft_id: str) -> dict[str, object]:
        """Delete a Gmail draft.

        This removes the draft artifact. Use only when the user explicitly wants it discarded.
        """
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

    @mcp.tool(annotations=tool_annotations("gmail_send_email"))
    def gmail_send_email(message: dict[str, object] | None = None) -> dict[str, object]:
        """Prepare sending an email through Gmail.

        This does not send immediately. It creates a preview and `operation_id`.
        Use `gmail_confirm_send_email` after review to execute delivery.
        If the user wants a draft instead, prefer `gmail_create_draft`.

        Example payload:
        ```json
        {
          "message": {
            "to": ["person@example.com"],
            "subject": "Confirmacion",
            "body_text": "Queda confirmado para manana."
          }
        }
        ```
        """
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

    @mcp.tool(annotations=tool_annotations("gmail_confirm_send_email"))
    def gmail_confirm_send_email(operation_id: str) -> dict[str, object]:
        """Confirm sending a prepared Gmail email.

        Use only after reviewing the preview returned by `gmail_send_email`.
        """
        payload = GmailConfirmSendEmailInput(operation_id=operation_id)
        return run_tool(
            tool_name="gmail_confirm_send_email",
            provider="google",
            resource_type="gmail_message",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: GmailService(session).confirm_send_email(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool(annotations=tool_annotations("gmail_delete_message"))
    def gmail_delete_message(message_id: str) -> dict[str, object]:
        """Move a Gmail message to trash.

        This is a mutation. It moves the message to trash and is not a permanent delete tool.
        Locate the message ID first with `gmail_list_messages` or `gmail_list_threads`.

        Example payload:
        ```json
        {
          "message_id": "msg-123"
        }
        ```
        """
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
