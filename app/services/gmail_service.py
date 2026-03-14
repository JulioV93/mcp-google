from __future__ import annotations

from sqlalchemy.orm import Session

from app.errors import AppError
from app.google.gmail_client import GmailClient, build_raw_message
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
class GmailService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.client = GmailClient(session)

    def list_messages(
        self,
        *,
        external_subject: str,
        input_data: GmailListMessagesInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.list_messages(
                external_subject=external_subject,
                tenant_id=tenant_id,
                query=input_data.query,
                max_results=input_data.max_results,
                page_token=input_data.page_token,
            )
        except AppError:
            raise

        items = [
            {
                "id": item.get("id"),
                "thread_id": item.get("threadId"),
            }
            for item in payload.get("messages", [])
        ]
        return {"items": items, "next_page_token": payload.get("nextPageToken")}

    def get_message(
        self,
        *,
        external_subject: str,
        input_data: GmailGetMessageInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.get_message(
                external_subject=external_subject,
                tenant_id=tenant_id,
                message_id=input_data.message_id,
            )
        except AppError:
            raise
        return _normalize_message(payload)

    def list_threads(
        self,
        *,
        external_subject: str,
        input_data: GmailListThreadsInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.list_threads(
                external_subject=external_subject,
                tenant_id=tenant_id,
                query=input_data.query,
                max_results=input_data.max_results,
                page_token=input_data.page_token,
            )
        except AppError:
            raise

        items = [
            {
                "id": item.get("id"),
                "history_id": item.get("historyId"),
                "snippet": item.get("snippet"),
            }
            for item in payload.get("threads", [])
        ]
        return {"items": items, "next_page_token": payload.get("nextPageToken")}

    def create_draft(
        self,
        *,
        external_subject: str,
        input_data: GmailCreateDraftInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        raw_message = build_raw_message(**input_data.message.model_dump())
        try:
            payload = self.client.create_draft(
                external_subject=external_subject,
                tenant_id=tenant_id,
                message_body=raw_message,
            )
        except AppError:
            raise
        return _normalize_draft(payload)

    def update_draft(
        self,
        *,
        external_subject: str,
        input_data: GmailUpdateDraftInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        raw_message = build_raw_message(**input_data.message.model_dump())
        try:
            payload = self.client.update_draft(
                external_subject=external_subject,
                tenant_id=tenant_id,
                draft_id=input_data.draft_id,
                message_body=raw_message,
            )
        except AppError:
            raise
        return _normalize_draft(payload)

    def delete_draft(
        self,
        *,
        external_subject: str,
        input_data: GmailDeleteDraftInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            self.client.delete_draft(
                external_subject=external_subject,
                tenant_id=tenant_id,
                draft_id=input_data.draft_id,
            )
        except AppError:
            raise
        return {"deleted": True, "draft_id": input_data.draft_id}

    def send_email(
        self,
        *,
        external_subject: str,
        input_data: GmailSendEmailInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        raw_message = build_raw_message(**input_data.message.model_dump())
        try:
            payload = self.client.send_message(
                external_subject=external_subject,
                tenant_id=tenant_id,
                message_body=raw_message,
            )
        except AppError:
            raise
        return {
            "id": payload.get("id"),
            "thread_id": payload.get("threadId"),
            "label_ids": payload.get("labelIds", []),
        }

    def delete_message(
        self,
        *,
        external_subject: str,
        input_data: GmailDeleteMessageInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.trash_message(
                external_subject=external_subject,
                tenant_id=tenant_id,
                message_id=input_data.message_id,
            )
        except AppError:
            raise
        return {
            "trashed": True,
            "message_id": payload.get("id", input_data.message_id),
            "thread_id": payload.get("threadId"),
            "label_ids": payload.get("labelIds", []),
        }


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
    message = payload.get("message", {}) if isinstance(payload.get("message"), dict) else {}
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
