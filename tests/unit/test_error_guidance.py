from __future__ import annotations

import json

from app.errors import DriveNativeEditNotSupportedError, ValidationError


def test_validation_error_serializes_guidance_fields() -> None:
    error = ValidationError(
        "Recurring events must use recurrence.",
        hint="Create one event and send RRULE recurrence instead of many separate events.",
        expected_fields=["calendar_id", "event.start", "event.end", "event.recurrence"],
        example_payload={"recurrence": ["RRULE:FREQ=DAILY"]},
        recommended_tool="calendar_create_event",
    )

    payload = json.loads(str(error.to_tool_error()))

    assert payload["error"] == "validation_error"
    assert payload["hint"].startswith("Create one event")
    assert payload["expected_fields"] == [
        "calendar_id",
        "event.start",
        "event.end",
        "event.recurrence",
    ]
    assert payload["example_payload"] == {"recurrence": ["RRULE:FREQ=DAILY"]}
    assert payload["recommended_tool"] == "calendar_create_event"


def test_drive_native_edit_error_includes_recommendation() -> None:
    error = DriveNativeEditNotSupportedError()

    payload = json.loads(str(error.to_tool_error()))

    assert payload["error"] == "google_drive_native_edit_not_supported"
    assert payload["recommended_tool"] == "drive_export_file"
    assert payload["example_payload"] == {"export_mime_type": "application/pdf"}
