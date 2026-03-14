from __future__ import annotations

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.google.credentials import GoogleCredentialsProvider
from app.google.errors import map_google_http_error


class CalendarClient:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.credentials_provider = GoogleCredentialsProvider(session, self.settings)

    def _service(self, *, external_subject: str, tenant_id: str | None = None):
        credentials = self.credentials_provider.get_for_user(
            external_subject=external_subject,
            tenant_id=tenant_id,
        )
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def list_calendars(self, *, external_subject: str, tenant_id: str | None = None) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            return service.calendarList().list().execute()
        except HttpError as exc:
            raise map_google_http_error(exc) from exc

    def list_events(
        self,
        *,
        external_subject: str,
        calendar_id: str,
        tenant_id: str | None = None,
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 20,
        page_token: str | None = None,
        query: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        kwargs: dict[str, object] = {
            "calendarId": calendar_id,
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": max_results,
        }
        if time_min:
            kwargs["timeMin"] = time_min
        if time_max:
            kwargs["timeMax"] = time_max
        if page_token:
            kwargs["pageToken"] = page_token
        if query:
            kwargs["q"] = query
        try:
            return service.events().list(**kwargs).execute()
        except HttpError as exc:
            raise map_google_http_error(exc) from exc

    def get_event(
        self,
        *,
        external_subject: str,
        calendar_id: str,
        event_id: str,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            return service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        except HttpError as exc:
            raise map_google_http_error(exc) from exc

    def create_event(
        self,
        *,
        external_subject: str,
        calendar_id: str,
        event_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            return service.events().insert(calendarId=calendar_id, body=event_body).execute()
        except HttpError as exc:
            raise map_google_http_error(exc) from exc

    def update_event(
        self,
        *,
        external_subject: str,
        calendar_id: str,
        event_id: str,
        event_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            return service.events().patch(
                calendarId=calendar_id,
                eventId=event_id,
                body=event_body,
            ).execute()
        except HttpError as exc:
            raise map_google_http_error(exc) from exc

    def delete_event(
        self,
        *,
        external_subject: str,
        calendar_id: str,
        event_id: str,
        tenant_id: str | None = None,
    ) -> None:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            service.events().delete(calendarId=calendar_id, eventId=event_id, sendUpdates="none").execute()
        except HttpError as exc:
            raise map_google_http_error(exc) from exc
