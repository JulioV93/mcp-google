from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from fastmcp import Client, FastMCP
from pydantic import ValidationError

from app.schemas.calendar import CalendarCreateEventInput, CalendarUpdateEventInput
from app.schemas.tasks import TasksCreateTaskInput, TasksUpdateTaskInput
from app.services.calendar_service import CalendarService
from app.services.tasks_service import TasksService
from app.tools.calendar_tools import register_calendar_tools
from app.tools.tasks_tools import register_tasks_tools


@pytest.mark.parametrize(
    "body",
    [
        {"due": "2026-11-14T00:00:00.000Z", "notes": "Updated notes"},
        {"due": None},
        {"notes": ""},
        {"title": "Existing title", "status": "needsAction"},
    ],
)
def test_task_patch_sends_only_explicit_fields(body):
    payload = TasksUpdateTaskInput.model_validate(
        {"tasklist_id": "list", "task_id": "task", "task": body}
    )
    service = TasksService(Mock())
    service.client = Mock()
    service.client.update_task.return_value = {"id": "task", "title": "Existing title"}
    service.update_task(external_subject="test", input_data=payload)
    assert service.client.update_task.call_args.kwargs["task_body"] == body


@pytest.mark.parametrize(
    "body",
    [
        {"description": "Updated description"},
        {"description": "", "location": "", "recurrence": []},
        {"start": {"dateTime": "2026-10-07T10:00:00-03:00", "timeZone": "America/Santiago"}},
        {"colorId": "5", "reminders": {"useDefault": False, "overrides": []}},
    ],
)
def test_calendar_patch_sends_only_explicit_fields(body):
    payload = CalendarUpdateEventInput.model_validate({"event_id": "event", "event": body})
    service = CalendarService(Mock())
    service.client = Mock()
    service.client.update_event.return_value = {"id": "event", "summary": "Existing summary"}
    service.update_event(external_subject="test", input_data=payload)
    assert service.client.update_event.call_args.kwargs["event_body"] == body


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"title": None},
        {"title": ""},
        {"notes": None},
        {"status": None},
        {"status": "invalid"},
        {"due": "2026-10-07"},
        {"due": "2026-10-07T10:00:00"},
        {"due": "2026-02-30T10:00:00Z"},
        {"unexpected": "secret"},
    ],
)
def test_task_patch_rejects_invalid_fields(body):
    with pytest.raises(ValidationError):
        TasksUpdateTaskInput.model_validate(
            {"tasklist_id": "list", "task_id": "task", "task": body}
        )


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"summary": None},
        {"description": None},
        {"start": None},
        {"start": {}},
        {"recurrence": None},
        {"unexpected": "secret"},
    ],
)
def test_calendar_patch_rejects_invalid_fields(body):
    with pytest.raises(ValidationError):
        CalendarUpdateEventInput.model_validate({"event_id": "event", "event": body})


def test_create_contracts_still_require_fields():
    with pytest.raises(ValidationError):
        TasksCreateTaskInput.model_validate({"tasklist_id": "list", "task": {"due": None}})
    with pytest.raises(ValidationError):
        CalendarCreateEventInput.model_validate({"event": {"description": "Notes"}})


@pytest.mark.parametrize(
    "tool,arguments,expected_field",
    [
        ("tasks_create_task", {"tasklist_id": "list", "task": {}}, "task.title"),
        (
            "tasks_update_task",
            {"tasklist_id": "list", "task_id": "task", "task": {"due": "secret"}},
            "task.due",
        ),
        ("calendar_create_event", {"event": {}}, "event.start"),
        (
            "calendar_update_event",
            {"event_id": "event", "event": {"secret-key": "secret"}},
            "event.<unknown_field>",
        ),
    ],
)
async def test_mcp_validation_result_is_structured_and_redacted(tool, arguments, expected_field):
    mcp = FastMCP("validation-test")
    register_tasks_tools(mcp)
    register_calendar_tools(mcp)
    async with Client(mcp) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)
    assert result.is_error
    serialized = result.content[0].text
    error = json.loads(serialized)
    assert error["error"] == "validation_error"
    assert error["retryable"] is False
    assert expected_field in error["expected_fields"]
    assert "secret" not in serialized
    assert "input" not in error.get("metadata", {})
