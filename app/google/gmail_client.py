from __future__ import annotations

import base64
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.config import Settings
from app.google.client_base import GoogleApiClientBase


def build_raw_message(
    *,
    to: list[str],
    subject: str,
    body_text: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    thread_id: str | None = None,
) -> dict[str, object]:
    message = EmailMessage()
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    if cc:
        message["Cc"] = ", ".join(cc)
    if bcc:
        message["Bcc"] = ", ".join(bcc)
    message.set_content(body_text)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    payload: dict[str, object] = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id
    return payload


class GmailClient(GoogleApiClientBase):
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        super().__init__(session, settings)

    def _service(self, *, external_subject: str, tenant_id: str | None = None):
        return self._get_service(
            "gmail", "v1", external_subject=external_subject, tenant_id=tenant_id
        )

    def list_messages(
        self,
        *,
        external_subject: str,
        tenant_id: str | None = None,
        query: str | None = None,
        max_results: int = 20,
        page_token: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        kwargs: dict[str, object] = {"userId": "me", "maxResults": max_results}
        if query:
            kwargs["q"] = query
        if page_token:
            kwargs["pageToken"] = page_token
        return self._execute(service.users().messages().list(**kwargs))

    def get_message(
        self,
        *,
        external_subject: str,
        message_id: str,
        tenant_id: str | None = None,
        format: str = "metadata",
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        kwargs: dict[str, object] = {"userId": "me", "id": message_id, "format": format}
        if format == "metadata":
            kwargs["metadataHeaders"] = ["Subject", "From", "To"]
        return self._execute(service.users().messages().get(**kwargs))

    def list_threads(
        self,
        *,
        external_subject: str,
        tenant_id: str | None = None,
        query: str | None = None,
        max_results: int = 20,
        page_token: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        kwargs: dict[str, object] = {"userId": "me", "maxResults": max_results}
        if query:
            kwargs["q"] = query
        if page_token:
            kwargs["pageToken"] = page_token
        return self._execute(service.users().threads().list(**kwargs))

    def create_draft(
        self,
        *,
        external_subject: str,
        message_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        return self._execute(
            service.users().drafts().create(userId="me", body={"message": message_body})
        )

    def update_draft(
        self,
        *,
        external_subject: str,
        draft_id: str,
        message_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        return self._execute(
            service.users()
            .drafts()
            .update(
                userId="me",
                id=draft_id,
                body={"id": draft_id, "message": message_body},
            )
        )

    def delete_draft(
        self,
        *,
        external_subject: str,
        draft_id: str,
        tenant_id: str | None = None,
    ) -> None:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        self._execute(service.users().drafts().delete(userId="me", id=draft_id))

    def send_message(
        self,
        *,
        external_subject: str,
        message_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        return self._execute(service.users().messages().send(userId="me", body=message_body))

    def trash_message(
        self,
        *,
        external_subject: str,
        message_id: str,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        return self._execute(service.users().messages().trash(userId="me", id=message_id))
