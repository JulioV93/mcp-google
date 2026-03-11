from __future__ import annotations

import base64
from email.message import EmailMessage

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.google.credentials import GoogleCredentialsProvider
from app.google.errors import map_google_http_error


class GmailClientError(Exception):
    """Raised when Gmail operations fail."""


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


class GmailClient:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.credentials_provider = GoogleCredentialsProvider(session, self.settings)

    def _service(self, *, external_subject: str, tenant_id: str | None = None):
        credentials = self.credentials_provider.get_for_user(
            external_subject=external_subject,
            tenant_id=tenant_id,
        )
        return build("gmail", "v1", credentials=credentials, cache_discovery=False)

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
        try:
            return service.users().messages().list(**kwargs).execute()
        except HttpError as exc:
            raise GmailClientError(str(map_google_http_error(exc))) from exc

    def get_message(
        self,
        *,
        external_subject: str,
        message_id: str,
        tenant_id: str | None = None,
        format: str = "metadata",
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            kwargs: dict[str, object] = {"userId": "me", "id": message_id, "format": format}
            if format == "metadata":
                kwargs["metadataHeaders"] = ["Subject", "From", "To"]
            return service.users().messages().get(**kwargs).execute()
        except HttpError as exc:
            raise GmailClientError(str(map_google_http_error(exc))) from exc

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
        try:
            return service.users().threads().list(**kwargs).execute()
        except HttpError as exc:
            raise GmailClientError(str(map_google_http_error(exc))) from exc

    def create_draft(
        self,
        *,
        external_subject: str,
        message_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            return service.users().drafts().create(userId="me", body={"message": message_body}).execute()
        except HttpError as exc:
            raise GmailClientError(str(map_google_http_error(exc))) from exc

    def update_draft(
        self,
        *,
        external_subject: str,
        draft_id: str,
        message_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            return service.users().drafts().update(
                userId="me",
                id=draft_id,
                body={"id": draft_id, "message": message_body},
            ).execute()
        except HttpError as exc:
            raise GmailClientError(str(map_google_http_error(exc))) from exc

    def delete_draft(
        self,
        *,
        external_subject: str,
        draft_id: str,
        tenant_id: str | None = None,
    ) -> None:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            service.users().drafts().delete(userId="me", id=draft_id).execute()
        except HttpError as exc:
            raise GmailClientError(str(map_google_http_error(exc))) from exc

    def send_message(
        self,
        *,
        external_subject: str,
        message_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            return service.users().messages().send(userId="me", body=message_body).execute()
        except HttpError as exc:
            raise GmailClientError(str(map_google_http_error(exc))) from exc

    def delete_message(
        self,
        *,
        external_subject: str,
        message_id: str,
        tenant_id: str | None = None,
    ) -> None:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            service.users().messages().delete(userId="me", id=message_id).execute()
        except HttpError as exc:
            raise GmailClientError(str(map_google_http_error(exc))) from exc
