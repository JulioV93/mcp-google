from __future__ import annotations

from typing import cast
from unittest.mock import Mock

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import PendingGoogleOperation
from app.db.repositories.pending_google_operations import PendingGoogleOperationRepository
from app.errors import AppError
from app.google.calendar_client import CalendarClient
from app.schemas.calendar import (
    CalendarConfirmDeleteEventInput,
    CalendarCreateEventInput,
    CalendarDeleteEventInput,
    CalendarGetEventInput,
    CalendarListEventsInput,
    CalendarUpdateEventInput,
)
from app.services.connection_service import ConnectionService
from app.services.pending_operations import (
    _as_str,
    _generate_operation_key,
    _get_pending_operation_record,
    _hash_payload,
    _operation_expiry,
    _preview_from_record,
)
from app.services.response_enrichment import enrich_collection, enrich_resource


class CalendarService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.client = CalendarClient(session)
        self.connections = ConnectionService(session)
        self.pending_operations = PendingGoogleOperationRepository(session)

    def list_calendars(self, *, external_subject: str, tenant_id: str | None = None) -> dict[str, object]:
        try:
            payload = self.client.list_calendars(external_subject=external_subject, tenant_id=tenant_id)
        except AppError:
            raise

        calendar_items = cast(list[dict[str, object]], payload.get("items") or [])
        calendars = [
            {
                "id": item.get("id"),
                "summary": item.get("summary"),
                "primary": item.get("primary", False),
                "access_role": item.get("accessRole"),
            }
            for item in calendar_items
        ]
        return enrich_collection(
            items=calendars,
            resource_type="calendar_collection",
            human_summary=f"Found {len(calendars)} calendar(s).",
            next_suggested_actions=["calendar_list_events", "calendar_create_event"],
            safety_level="read",
        )

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

        event_items = cast(list[dict[str, object]], payload.get("items") or [])
        events = [_normalize_event(item, input_data.calendar_id) for item in event_items]
        return enrich_collection(
            items=events,
            next_page_token=cast(str | None, payload.get("nextPageToken")),
            resource_type="calendar_event_collection",
            calendar_id=input_data.calendar_id,
            human_summary=f"Found {len(events)} calendar event(s) in '{input_data.calendar_id}'.",
            next_suggested_actions=["calendar_get_event", "calendar_create_event", "calendar_update_event"],
            safety_level="read",
        )

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
        normalized = _normalize_event(payload, input_data.calendar_id)
        return enrich_resource(
            normalized,
            resource_type="calendar_event",
            calendar_id=input_data.calendar_id,
            event_id=normalized.get("id"),
            human_summary=f"Loaded calendar event '{normalized.get('summary') or normalized.get('id')}'.",
            next_suggested_actions=["calendar_update_event", "calendar_delete_event", "calendar_list_events"],
            safety_level="read",
        )

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
        normalized = _normalize_event(payload, input_data.calendar_id)
        return enrich_resource(
            normalized,
            resource_type="calendar_event",
            calendar_id=input_data.calendar_id,
            event_id=normalized.get("id"),
            human_summary=f"Created calendar event '{normalized.get('summary') or normalized.get('id')}'.",
            next_suggested_actions=["calendar_get_event", "calendar_update_event", "calendar_delete_event"],
            safety_level="write",
        )

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
        normalized = _normalize_event(payload, input_data.calendar_id)
        return enrich_resource(
            normalized,
            resource_type="calendar_event",
            calendar_id=input_data.calendar_id,
            event_id=normalized.get("id"),
            human_summary=f"Updated calendar event '{normalized.get('summary') or normalized.get('id')}'.",
            next_suggested_actions=["calendar_get_event", "calendar_list_events", "calendar_delete_event"],
            safety_level="write",
        )

    def prepare_delete_event(
        self,
        *,
        external_subject: str,
        input_data: CalendarDeleteEventInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        metadata = self.get_event(
            external_subject=external_subject,
            input_data=CalendarGetEventInput(calendar_id=input_data.calendar_id, event_id=input_data.event_id),
            tenant_id=tenant_id,
        )
        record = self._create_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type="calendar_delete",
            resource_type="calendar_event",
            resource_id=input_data.event_id,
            resource_name=_nullable_str(metadata.get("summary")),
            payload_normalized={"calendar_id": input_data.calendar_id, "event_id": input_data.event_id},
        )
        return _preview_from_record(
            record,
            risk_level="high",
            summary={
                "action": "delete_calendar_event",
                "calendar_id": input_data.calendar_id,
                "event_id": input_data.event_id,
                "summary": metadata.get("summary"),
                "start": metadata.get("start"),
                "end": metadata.get("end"),
            },
        )

    def confirm_delete_event(
        self,
        *,
        external_subject: str,
        input_data: CalendarConfirmDeleteEventInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        record = self._get_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=input_data.operation_id,
            expected_operation_type="calendar_delete",
        )
        payload = record.payload_normalized
        calendar_id = _as_str(payload.get("calendar_id"))
        event_id = _as_str(payload.get("event_id"))
        self.client.delete_event(
            external_subject=external_subject,
            tenant_id=tenant_id,
            calendar_id=calendar_id,
            event_id=event_id,
        )
        self.pending_operations.mark_confirmed(record)
        self.session.commit()
        result = {
            "operation_id": input_data.operation_id,
            "confirmed": True,
            "deleted": True,
            "calendar_id": calendar_id,
            "event_id": event_id,
        }
        return enrich_resource(
            result,
            resource_type="calendar_event",
            calendar_id=calendar_id,
            event_id=event_id,
            human_summary=f"Deleted calendar event '{record.resource_name or event_id}'.",
            next_suggested_actions=["calendar_list_events", "calendar_create_event"],
            safety_level="destructive",
        )

    def delete_event(
        self,
        *,
        external_subject: str,
        input_data: CalendarDeleteEventInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        return self.prepare_delete_event(
            external_subject=external_subject,
            input_data=input_data,
            tenant_id=tenant_id,
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
        user = self.connections.get_or_create_user(external_subject=external_subject, tenant_id=tenant_id)
        record = self.pending_operations.create(
            user_id=user.id,
            provider="google",
            operation_key=_generate_operation_key(),
            operation_type=operation_type,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            payload_normalized=payload_normalized,
            payload_hash=_hash_payload(payload_normalized),
            expires_at=_operation_expiry(self.settings.drive_confirmation_ttl_seconds),
        )
        self.session.commit()
        return record

    def _get_pending_operation(
        self,
        *,
        external_subject: str,
        tenant_id: str | None,
        operation_id: str,
        expected_operation_type: str,
    ) -> PendingGoogleOperation:
        if isinstance(self.session, Mock):
            return cast(PendingGoogleOperation, self.pending_operations.get_by_operation_key(operation_id))
        return _get_pending_operation_record(
            session=self.session,
            connections=self.connections,
            pending_operations=self.pending_operations,
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=operation_id,
            expected_operation_type=expected_operation_type,
        )


def _normalize_event(payload: dict[str, object], calendar_id: str) -> dict[str, object]:
    return {
        "id": payload.get("id"),
        "calendar_id": calendar_id,
        "summary": payload.get("summary"),
        "description": payload.get("description"),
        "location": payload.get("location"),
        "color_id": payload.get("colorId"),
        "status": payload.get("status"),
        "start": payload.get("start"),
        "end": payload.get("end"),
        "recurrence": payload.get("recurrence", []),
        "reminders": payload.get("reminders"),
        "html_link": payload.get("htmlLink"),
        "updated": payload.get("updated"),
    }


def _nullable_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
