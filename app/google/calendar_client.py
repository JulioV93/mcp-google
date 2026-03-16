from __future__ import annotations

from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.config import Settings
from app.google.client_base import GoogleApiClientBase


class CalendarClient(GoogleApiClientBase):
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        super().__init__(session, settings)

    def _service(self, *, external_subject: str, tenant_id: str | None = None):
        credentials = self.credentials_provider.get_for_user(
            external_subject=external_subject,
            tenant_id=tenant_id,
        )
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def list_calendars(self, *, external_subject: str, tenant_id: str | None = None) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        return self._execute(service.calendarList().list())

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
        return self._execute(service.events().list(**kwargs))

    def get_event(
        self,
        *,
        external_subject: str,
        calendar_id: str,
        event_id: str,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        return self._execute(service.events().get(calendarId=calendar_id, eventId=event_id))

    def create_event(
        self,
        *,
        external_subject: str,
        calendar_id: str,
        event_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        return self._execute(service.events().insert(calendarId=calendar_id, body=event_body))

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
        return self._execute(
            service.events().patch(
                calendarId=calendar_id,
                eventId=event_id,
                body=event_body,
            )
        )

    def delete_event(
        self,
        *,
        external_subject: str,
        calendar_id: str,
        event_id: str,
        tenant_id: str | None = None,
    ) -> None:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        self._execute(service.events().delete(calendarId=calendar_id, eventId=event_id, sendUpdates="none"))
