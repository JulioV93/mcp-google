from __future__ import annotations

from unittest.mock import Mock

from app.schemas.calendar import (
    CalendarCreateEventInput,
    CalendarEventDateTime,
    CalendarEventInput,
    CalendarEventReminderOverride,
    CalendarEventReminders,
    CalendarListEventsInput,
    CalendarUpdateEventInput,
)
from app.services.calendar_service import CalendarService


def test_list_events_normalizes_payload() -> None:
    session = Mock()
    service = CalendarService(session)
    service.client = Mock()
    service.client.list_events.return_value = {
        "items": [
            {
                "id": "evt-1",
                "summary": "Team Sync",
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

    assert result["next_page_token"] == "next-123"
    assert result["items"][0]["id"] == "evt-1"
    assert result["items"][0]["calendar_id"] == "primary"
    assert result["items"][0]["recurrence"] == ["RRULE:FREQ=DAILY"]
    assert result["items"][0]["reminders"]["useDefault"] is False


def test_create_event_passes_serialized_body() -> None:
    session = Mock()
    service = CalendarService(session)
    service.client = Mock()
    service.client.create_event.return_value = {
        "id": "evt-2",
        "summary": "Launch Review",
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

    assert result["id"] == "evt-2"
    assert result["recurrence"] == ["RRULE:FREQ=DAILY"]
    assert result["reminders"]["useDefault"] is False
    service.client.create_event.assert_called_once_with(
        external_subject="user-1",
        tenant_id=None,
        calendar_id="primary",
        event_body={
            "summary": "Launch Review",
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
        event=CalendarEventInput(
            summary="Morning Routine",
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

    assert result["id"] == "evt-3"
    assert result["recurrence"] == ["RRULE:FREQ=DAILY"]
    assert result["reminders"]["useDefault"] is False
    service.client.update_event.assert_called_once_with(
        external_subject="user-1",
        tenant_id=None,
        calendar_id="primary",
        event_id="evt-3",
        event_body={
            "summary": "Morning Routine",
            "start": {"dateTime": "2026-03-14T08:00:00-03:00"},
            "end": {"dateTime": "2026-03-14T08:10:00-03:00"},
            "recurrence": ["RRULE:FREQ=DAILY"],
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": 5}],
            },
        },
    )
