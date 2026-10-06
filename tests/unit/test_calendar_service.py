from __future__ import annotations

from typing import cast
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.base import Base
from app.schemas.calendar import (
    CalendarConfirmDeleteEventInput,
    CalendarCreateEventInput,
    CalendarDeleteEventInput,
    CalendarEventDateTime,
    CalendarEventInput,
    CalendarEventPatchInput,
    CalendarEventReminderOverride,
    CalendarEventReminders,
    CalendarListEventsInput,
    CalendarUpdateEventInput,
)
from app.services.calendar_service import CalendarService


def create_test_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", future=True, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    return session_factory()


def test_list_events_normalizes_payload() -> None:
    session = Mock()
    service = CalendarService(session)
    service.client = Mock()
    service.client.list_events.return_value = {
        "items": [
            {
                "id": "evt-1",
                "summary": "Team Sync",
                "colorId": "5",
                "start": {"dateTime": "2026-03-12T10:00:00Z"},
                "end": {"dateTime": "2026-03-12T11:00:00Z"},
                "recurrence": ["RRULE:FREQ=DAILY"],
                "reminders": {
                    "useDefault": False,
                    "overrides": [{"method": "popup", "minutes": 5}],
                },
                "htmlLink": "https://calendar.google.com/event?eid=1",
            }
        ],
        "nextPageToken": "next-123",
    }

    result = service.list_events(
        external_subject="user-1",
        input_data=CalendarListEventsInput(calendar_id="primary"),
    )
    items = cast(list[dict[str, object]], result["items"])
    first_event = cast(dict[str, object], items[0])
    reminders = cast(dict[str, object], first_event["reminders"])

    assert result["next_page_token"] == "next-123"
    assert result["resource_identity"] == {
        "type": "calendar_event_collection",
        "calendar_id": "primary",
    }
    assert result["safety_level"] == "read"
    assert first_event["id"] == "evt-1"
    assert first_event["calendar_id"] == "primary"
    assert first_event["color_id"] == "5"
    assert first_event["recurrence"] == ["RRULE:FREQ=DAILY"]
    assert reminders["useDefault"] is False


def test_create_event_passes_serialized_body() -> None:
    session = Mock()
    service = CalendarService(session)
    service.client = Mock()
    service.client.create_event.return_value = {
        "id": "evt-2",
        "summary": "Launch Review",
        "colorId": "11",
        "start": {"dateTime": "2026-03-13T09:00:00Z"},
        "end": {"dateTime": "2026-03-13T10:00:00Z"},
        "recurrence": ["RRULE:FREQ=DAILY"],
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 5}],
        },
    }

    payload = CalendarCreateEventInput(
        calendar_id="primary",
        event=CalendarEventInput(
            summary="Launch Review",
            colorId="11",
            start=CalendarEventDateTime(dateTime="2026-03-13T09:00:00Z"),
            end=CalendarEventDateTime(dateTime="2026-03-13T10:00:00Z"),
            recurrence=["RRULE:FREQ=DAILY"],
            reminders=CalendarEventReminders(
                useDefault=False,
                overrides=[CalendarEventReminderOverride(method="popup", minutes=5)],
            ),
        ),
    )

    result = service.create_event(external_subject="user-1", input_data=payload)
    create_result = cast(dict[str, object], result)
    reminders = cast(dict[str, object], create_result["reminders"])

    assert create_result["id"] == "evt-2"
    assert create_result["resource_identity"] == {
        "type": "calendar_event",
        "calendar_id": "primary",
        "event_id": "evt-2",
    }
    assert create_result["safety_level"] == "write"
    assert create_result["color_id"] == "11"
    assert create_result["recurrence"] == ["RRULE:FREQ=DAILY"]
    assert reminders["useDefault"] is False
    service.client.create_event.assert_called_once_with(
        external_subject="user-1",
        tenant_id=None,
        calendar_id="primary",
        event_body={
            "summary": "Launch Review",
            "colorId": "11",
            "start": {"dateTime": "2026-03-13T09:00:00Z"},
            "end": {"dateTime": "2026-03-13T10:00:00Z"},
            "recurrence": ["RRULE:FREQ=DAILY"],
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": 5}],
            },
        },
    )


def test_update_event_passes_recurrence_and_reminders() -> None:
    session = Mock()
    service = CalendarService(session)
    service.client = Mock()
    service.client.update_event.return_value = {
        "id": "evt-3",
        "summary": "Morning Routine",
        "colorId": "3",
        "start": {"dateTime": "2026-03-14T08:00:00-03:00"},
        "end": {"dateTime": "2026-03-14T08:10:00-03:00"},
        "recurrence": ["RRULE:FREQ=DAILY"],
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 5}],
        },
    }

    payload = CalendarUpdateEventInput(
        calendar_id="primary",
        event_id="evt-3",
        event=CalendarEventPatchInput(
            summary="Morning Routine",
            colorId="3",
            start=CalendarEventDateTime(dateTime="2026-03-14T08:00:00-03:00"),
            end=CalendarEventDateTime(dateTime="2026-03-14T08:10:00-03:00"),
            recurrence=["RRULE:FREQ=DAILY"],
            reminders=CalendarEventReminders(
                useDefault=False,
                overrides=[CalendarEventReminderOverride(method="popup", minutes=5)],
            ),
        ),
    )

    result = service.update_event(external_subject="user-1", input_data=payload)
    update_result = cast(dict[str, object], result)
    reminders = cast(dict[str, object], update_result["reminders"])

    assert update_result["id"] == "evt-3"
    assert update_result["resource_identity"] == {
        "type": "calendar_event",
        "calendar_id": "primary",
        "event_id": "evt-3",
    }
    assert update_result["color_id"] == "3"
    assert update_result["recurrence"] == ["RRULE:FREQ=DAILY"]
    assert reminders["useDefault"] is False
    service.client.update_event.assert_called_once_with(
        external_subject="user-1",
        tenant_id=None,
        calendar_id="primary",
        event_id="evt-3",
        event_body={
            "summary": "Morning Routine",
            "colorId": "3",
            "start": {"dateTime": "2026-03-14T08:00:00-03:00"},
            "end": {"dateTime": "2026-03-14T08:10:00-03:00"},
            "recurrence": ["RRULE:FREQ=DAILY"],
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": 5}],
            },
        },
    )


def test_delete_event_requires_confirmation_and_confirm_executes() -> None:
    session = create_test_session()
    service = CalendarService(session, settings=Settings())
    service.client = Mock()
    service.client.get_event.return_value = {
        "id": "evt-9",
        "summary": "Delete me",
        "start": {"dateTime": "2026-03-14T08:00:00-03:00"},
        "end": {"dateTime": "2026-03-14T08:10:00-03:00"},
    }

    prepare = service.delete_event(
        external_subject="user-1",
        input_data=CalendarDeleteEventInput(calendar_id="primary", event_id="evt-9"),
    )

    assert prepare["requires_confirmation"] is True
    operation_id = cast(str, prepare["operation_id"])

    confirm = service.confirm_delete_event(
        external_subject="user-1",
        input_data=CalendarConfirmDeleteEventInput(operation_id=operation_id),
    )

    assert confirm["confirmed"] is True
    assert confirm["deleted"] is True
    assert confirm["resource_identity"] == {
        "type": "calendar_event",
        "calendar_id": "primary",
        "event_id": "evt-9",
    }
    service.client.delete_event.assert_called_once_with(
        external_subject="user-1",
        tenant_id=None,
        calendar_id="primary",
        event_id="evt-9",
    )
