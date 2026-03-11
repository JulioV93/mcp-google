from __future__ import annotations

from unittest.mock import Mock

from app.schemas.calendar import CalendarCreateEventInput, CalendarEventInput, CalendarEventDateTime, CalendarListEventsInput
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


def test_create_event_passes_serialized_body() -> None:
    session = Mock()
    service = CalendarService(session)
    service.client = Mock()
    service.client.create_event.return_value = {
        "id": "evt-2",
        "summary": "Launch Review",
        "start": {"dateTime": "2026-03-13T09:00:00Z"},
        "end": {"dateTime": "2026-03-13T10:00:00Z"},
    }

    payload = CalendarCreateEventInput(
        calendar_id="primary",
        event=CalendarEventInput(
            summary="Launch Review",
            start=CalendarEventDateTime(dateTime="2026-03-13T09:00:00Z"),
            end=CalendarEventDateTime(dateTime="2026-03-13T10:00:00Z"),
        ),
    )

    result = service.create_event(external_subject="user-1", input_data=payload)

    assert result["id"] == "evt-2"
    service.client.create_event.assert_called_once()
