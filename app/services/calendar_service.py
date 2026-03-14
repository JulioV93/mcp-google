from __future__ import annotations

from sqlalchemy.orm import Session

from app.errors import AppError
from app.google.calendar_client import CalendarClient
from app.schemas.calendar import (
    CalendarCreateEventInput,
    CalendarDeleteEventInput,
    CalendarGetEventInput,
    CalendarListEventsInput,
    CalendarUpdateEventInput,
)


class CalendarService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.client = CalendarClient(session)

    def list_calendars(self, *, external_subject: str, tenant_id: str | None = None) -> dict[str, object]:
        try:
            payload = self.client.list_calendars(external_subject=external_subject, tenant_id=tenant_id)
        except AppError:
            raise

        calendars = [
            {
                "id": item.get("id"),
                "summary": item.get("summary"),
                "primary": item.get("primary", False),
                "access_role": item.get("accessRole"),
            }
            for item in payload.get("items", [])
        ]
        return {"items": calendars}

    def list_events(
        self,
        *,
        external_subject: str,
        input_data: CalendarListEventsInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.list_events(
                external_subject=external_subject,
                tenant_id=tenant_id,
                calendar_id=input_data.calendar_id,
                time_min=input_data.time_min,
                time_max=input_data.time_max,
                max_results=input_data.max_results,
                page_token=input_data.page_token,
                query=input_data.query,
            )
        except AppError:
            raise

        events = [_normalize_event(item, input_data.calendar_id) for item in payload.get("items", [])]
        return {
            "items": events,
            "next_page_token": payload.get("nextPageToken"),
        }

    def get_event(
        self,
        *,
        external_subject: str,
        input_data: CalendarGetEventInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.get_event(
                external_subject=external_subject,
                tenant_id=tenant_id,
                calendar_id=input_data.calendar_id,
                event_id=input_data.event_id,
            )
        except AppError:
            raise
        return _normalize_event(payload, input_data.calendar_id)

    def create_event(
        self,
        *,
        external_subject: str,
        input_data: CalendarCreateEventInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.create_event(
                external_subject=external_subject,
                tenant_id=tenant_id,
                calendar_id=input_data.calendar_id,
                event_body=input_data.event.model_dump(by_alias=True, exclude_none=True),
            )
        except AppError:
            raise
        return _normalize_event(payload, input_data.calendar_id)

    def update_event(
        self,
        *,
        external_subject: str,
        input_data: CalendarUpdateEventInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.update_event(
                external_subject=external_subject,
                tenant_id=tenant_id,
                calendar_id=input_data.calendar_id,
                event_id=input_data.event_id,
                event_body=input_data.event.model_dump(by_alias=True, exclude_none=True),
            )
        except AppError:
            raise
        return _normalize_event(payload, input_data.calendar_id)

    def delete_event(
        self,
        *,
        external_subject: str,
        input_data: CalendarDeleteEventInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            self.client.delete_event(
                external_subject=external_subject,
                tenant_id=tenant_id,
                calendar_id=input_data.calendar_id,
                event_id=input_data.event_id,
            )
        except AppError:
            raise
        return {
            "deleted": True,
            "calendar_id": input_data.calendar_id,
            "event_id": input_data.event_id,
        }


def _normalize_event(payload: dict[str, object], calendar_id: str) -> dict[str, object]:
    return {
        "id": payload.get("id"),
        "calendar_id": calendar_id,
        "summary": payload.get("summary"),
        "description": payload.get("description"),
        "location": payload.get("location"),
        "status": payload.get("status"),
        "start": payload.get("start"),
        "end": payload.get("end"),
        "recurrence": payload.get("recurrence", []),
        "reminders": payload.get("reminders"),
        "html_link": payload.get("htmlLink"),
        "updated": payload.get("updated"),
    }
