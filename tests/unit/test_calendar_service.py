from __future__ import annotations

from typing import cast
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
        event=CalendarEventInput(
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
