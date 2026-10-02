from __future__ import annotations

from typing import cast

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import PendingGoogleOperation
from app.db.repositories.pending_google_operations import PendingGoogleOperationRepository
from app.google.gmail_client import GmailClient, build_raw_message
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
from app.services.connection_service import ConnectionService
from app.services.pending_operations import (
    _get_pending_operation_record,
    _preview_from_record,
    confirmed_operation,
    create_pending_operation,
)
from app.services.response_enrichment import enrich_collection, enrich_resource


class GmailService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.client = GmailClient(session, self.settings)
        self.connections = ConnectionService(session)
        self.pending_operations = PendingGoogleOperationRepository(session)

    def list_messages(
        self,
        *,
        external_subject: str,
        input_data: GmailListMessagesInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        payload = self.client.list_messages(
            external_subject=external_subject,
            tenant_id=tenant_id,
            query=input_data.query,
            max_results=input_data.max_results,
            page_token=input_data.page_token,
        )

        raw_message_items = payload.get("messages")
        items = [
            {
                "id": item.get("id"),
                "thread_id": item.get("threadId"),
            }
            for item in cast(
                list[dict[str, object]],
                raw_message_items if isinstance(raw_message_items, list) else [],
            )
        ]
        next_page_token_raw = payload.get("nextPageToken")
        next_page_token = cast(
            str | None, next_page_token_raw if isinstance(next_page_token_raw, str) else None
        )
        return enrich_collection(
            items=items,
            next_page_token=next_page_token,
            resource_type="gmail_message_collection",
            human_summary=f"Found {len(items)} Gmail message(s).",
            next_suggested_actions=[
                "gmail_get_message",
                "gmail_list_threads",
                "gmail_create_draft",
            ],
            safety_level="read",
        )

    def get_message(
        self,
        *,
        external_subject: str,
        input_data: GmailGetMessageInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        payload = self.client.get_message(
            external_subject=external_subject,
            tenant_id=tenant_id,
            message_id=input_data.message_id,
        )
        normalized = _normalize_message(payload)
        return enrich_resource(
            normalized,
            resource_type="gmail_message",
            message_id=normalized.get("id"),
            thread_id=normalized.get("thread_id"),
            human_summary=f"Loaded Gmail message '{normalized.get('subject') or normalized.get('id')}'.",
            next_suggested_actions=[
                "gmail_create_draft",
                "gmail_delete_message",
                "gmail_list_threads",
            ],
            safety_level="read",
        )

    def list_threads(
        self,
        *,
        external_subject: str,
        input_data: GmailListThreadsInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        payload = self.client.list_threads(
            external_subject=external_subject,
            tenant_id=tenant_id,
            query=input_data.query,
            max_results=input_data.max_results,
            page_token=input_data.page_token,
        )

        raw_thread_items = payload.get("threads")
        items = [
            {
                "id": item.get("id"),
                "history_id": item.get("historyId"),
                "snippet": item.get("snippet"),
            }
            for item in cast(
                list[dict[str, object]],
                raw_thread_items if isinstance(raw_thread_items, list) else [],
            )
        ]
        next_page_token_raw = payload.get("nextPageToken")
        next_page_token = cast(
            str | None, next_page_token_raw if isinstance(next_page_token_raw, str) else None
        )
        return enrich_collection(
            items=items,
            next_page_token=next_page_token,
            resource_type="gmail_thread_collection",
            human_summary=f"Found {len(items)} Gmail thread(s).",
            next_suggested_actions=["gmail_get_message", "gmail_create_draft", "gmail_send_email"],
            safety_level="read",
        )

    def create_draft(
        self,
        *,
        external_subject: str,
        input_data: GmailCreateDraftInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        raw_message = build_raw_message(**input_data.message.model_dump())
        payload = self.client.create_draft(
            external_subject=external_subject,
            tenant_id=tenant_id,
            message_body=raw_message,
        )
        normalized = _normalize_draft(payload)
        message_payload = cast(
            dict[str, object] | None,
            normalized.get("message") if isinstance(normalized.get("message"), dict) else None,
        )
        message_id = message_payload.get("id") if message_payload is not None else None
        return enrich_resource(
            normalized,
            resource_type="gmail_draft",
            draft_id=normalized.get("id"),
            message_id=message_id,
            human_summary=f"Created Gmail draft '{_draft_summary(normalized)}'.",
            next_suggested_actions=["gmail_update_draft", "gmail_send_email", "gmail_delete_draft"],
            safety_level="write",
        )

    def update_draft(
        self,
        *,
        external_subject: str,
        input_data: GmailUpdateDraftInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        raw_message = build_raw_message(**input_data.message.model_dump())
        payload = self.client.update_draft(
            external_subject=external_subject,
            tenant_id=tenant_id,
            draft_id=input_data.draft_id,
            message_body=raw_message,
        )
        normalized = _normalize_draft(payload)
        message_payload = cast(
            dict[str, object] | None,
            normalized.get("message") if isinstance(normalized.get("message"), dict) else None,
        )
        message_id = message_payload.get("id") if message_payload is not None else None
        return enrich_resource(
            normalized,
            resource_type="gmail_draft",
            draft_id=normalized.get("id"),
            message_id=message_id,
            human_summary=f"Updated Gmail draft '{_draft_summary(normalized)}'.",
            next_suggested_actions=["gmail_send_email", "gmail_delete_draft", "gmail_update_draft"],
            safety_level="write",
        )

    def delete_draft(
        self,
        *,
        external_subject: str,
        input_data: GmailDeleteDraftInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        self.client.delete_draft(
            external_subject=external_subject,
            tenant_id=tenant_id,
            draft_id=input_data.draft_id,
        )
        return enrich_resource(
            {"deleted": True, "draft_id": input_data.draft_id},
            resource_type="gmail_draft",
            draft_id=input_data.draft_id,
            human_summary=f"Deleted Gmail draft '{input_data.draft_id}'.",
            next_suggested_actions=["gmail_create_draft", "gmail_send_email"],
            safety_level="destructive",
        )

    def send_email(
        self,
        *,
        external_subject: str,
        input_data: GmailSendEmailInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        payload_normalized = input_data.model_dump(exclude_none=True)
        record = self._create_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type="gmail_send",
            resource_type="gmail_message",
            payload_normalized=payload_normalized,
            resource_name=_gmail_subject(payload_normalized),
        )
        return _preview_from_record(
            record,
            risk_level="high",
            summary={
                "action": "send_email",
                "to": _gmail_recipients(payload_normalized, "to"),
                "subject": _gmail_subject(payload_normalized),
                "cc": _gmail_recipients(payload_normalized, "cc"),
                "bcc": _gmail_recipients(payload_normalized, "bcc"),
                "thread_id": _gmail_thread_id(payload_normalized),
            },
        )

    @confirmed_operation
    def confirm_send_email(
        self,
        *,
        external_subject: str,
        input_data: GmailConfirmSendEmailInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        record = self._get_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=input_data.operation_id,
            expected_operation_type="gmail_send",
        )
        payload = record.payload_normalized
        raw_message = build_raw_message(
            to=_gmail_recipients(payload, "to"),
            subject=_gmail_subject(payload) or "",
            body_text=_gmail_body_text(payload) or "",
            cc=_gmail_recipients(payload, "cc") or None,
            bcc=_gmail_recipients(payload, "bcc") or None,
            thread_id=_gmail_thread_id(payload),
        )
        result_payload = self.client.send_message(
            external_subject=external_subject,
            tenant_id=tenant_id,
            message_body=raw_message,
        )
        self.pending_operations.mark_confirmed(record)
        self.session.commit()
        result = {
            "operation_id": input_data.operation_id,
            "confirmed": True,
            "id": result_payload.get("id"),
            "thread_id": result_payload.get("threadId"),
            "label_ids": result_payload.get("labelIds", []),
        }
        return enrich_resource(
            result,
            resource_type="gmail_message",
            message_id=result.get("id"),
            thread_id=result.get("thread_id"),
            human_summary=f"Sent Gmail message '{record.resource_name or result.get('id')}'.",
            next_suggested_actions=["gmail_get_message", "gmail_list_threads"],
            safety_level="destructive",
        )

    def _get_pending_operation(
        self,
        *,
        external_subject: str,
        tenant_id: str | None,
        operation_id: str,
        expected_operation_type: str,
    ) -> PendingGoogleOperation:
        return _get_pending_operation_record(
            session=self.session,
            connections=self.connections,
            pending_operations=self.pending_operations,
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=operation_id,
            expected_operation_type=expected_operation_type,
        )

    def _create_pending_operation(
        self,
        *,
        external_subject: str,
        tenant_id: str | None,
        operation_type: str,
        resource_type: str,
        payload_normalized: dict[str, object],
        resource_id: str | None = None,
        resource_name: str | None = None,
    ) -> PendingGoogleOperation:
        return create_pending_operation(
            self,
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type=operation_type,
            resource_type=resource_type,
            payload_normalized=payload_normalized,
            resource_id=resource_id,
            resource_name=resource_name,
        )

    def delete_message(
        self,
        *,
        external_subject: str,
        input_data: GmailDeleteMessageInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        payload = self.client.trash_message(
            external_subject=external_subject,
            tenant_id=tenant_id,
            message_id=input_data.message_id,
        )
        result = {
            "trashed": True,
            "message_id": payload.get("id", input_data.message_id),
            "thread_id": payload.get("threadId"),
            "label_ids": payload.get("labelIds", []),
        }
        return enrich_resource(
            result,
            resource_type="gmail_message",
            message_id=result.get("message_id"),
            thread_id=result.get("thread_id"),
            human_summary=f"Moved Gmail message '{result.get('message_id')}' to trash.",
            next_suggested_actions=["gmail_list_messages", "gmail_list_threads"],
            safety_level="destructive",
        )


def _normalize_message(payload: dict[str, object]) -> dict[str, object]:
    headers = _header_map(payload)
    return {
        "id": payload.get("id"),
        "thread_id": payload.get("threadId"),
        "label_ids": payload.get("labelIds", []),
        "snippet": payload.get("snippet"),
        "subject": headers.get("subject"),
        "from": headers.get("from"),
        "to": headers.get("to"),
        "internal_date": payload.get("internalDate"),
    }


def _normalize_draft(payload: dict[str, object]) -> dict[str, object]:
    message_value = payload.get("message")
    message = cast(dict[str, object], message_value) if isinstance(message_value, dict) else {}
    normalized_message = _normalize_message(message)
    return {
        "id": payload.get("id"),
        "message": normalized_message,
    }


def _header_map(payload: dict[str, object]) -> dict[str, str]:
    message_payload = payload.get("payload")
    if not isinstance(message_payload, dict):
        return {}
    headers = message_payload.get("headers", [])
    if not isinstance(headers, list):
        return {}

    result: dict[str, str] = {}
    for header in headers:
        if not isinstance(header, dict):
            continue
        name = str(header.get("name") or "").lower()
        value = str(header.get("value") or "")
        if name:
            result[name] = value
    return result


def _draft_summary(payload: dict[str, object]) -> str:
    message = payload.get("message")
    if isinstance(message, dict):
        subject = message.get("subject")
        if isinstance(subject, str) and subject:
            return subject
    draft_id = payload.get("id")
    return str(draft_id) if draft_id is not None else "draft"


def _nullable_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _gmail_message_payload(payload: dict[str, object]) -> dict[str, object]:
    message = payload.get("message")
    return cast(dict[str, object], message) if isinstance(message, dict) else {}


def _gmail_subject(payload: dict[str, object]) -> str | None:
    message = _gmail_message_payload(payload)
    subject = message.get("subject")
    return subject if isinstance(subject, str) and subject else None


def _gmail_thread_id(payload: dict[str, object]) -> str | None:
    message = _gmail_message_payload(payload)
    thread_id = message.get("thread_id") or message.get("threadId")
    return thread_id if isinstance(thread_id, str) and thread_id else None


def _gmail_body_text(payload: dict[str, object]) -> str | None:
    message = _gmail_message_payload(payload)
    body_text = message.get("body_text")
    return body_text if isinstance(body_text, str) and body_text else None


def _gmail_recipients(payload: dict[str, object], key: str) -> list[str]:
    message = _gmail_message_payload(payload)
    recipients = message.get(key)
    if not isinstance(recipients, list):
        return []
    return [str(item) for item in recipients if isinstance(item, str)]
