from __future__ import annotations

from unittest.mock import Mock

from app.schemas.tasks import (
    TaskInput,
    TasksCompleteTaskInput,
    TasksCreateTaskInput,
    TasksCreateTasklistInput,
    TasksListTasklistsInput,
)
from app.services.tasks_service import TasksService


def test_list_tasklists_normalizes_payload() -> None:
    session = Mock()
    service = TasksService(session)
    service.client = Mock()
    service.client.list_tasklists.return_value = {
        "items": [
            {
                "id": "list-1",
                "title": "Personal",
                "updated": "2026-03-11T10:00:00Z",
                "selfLink": "https://tasks.googleapis.com/tasks/v1/users/@me/lists/list-1",
            }
        ],
        "nextPageToken": "next-lists",
    }

    result = service.list_tasklists(
        external_subject="user-1",
        input_data=TasksListTasklistsInput(),
    )

    assert result["next_page_token"] == "next-lists"
    assert result["items"][0]["id"] == "list-1"


def test_create_task_serializes_task_payload() -> None:
    session = Mock()
    service = TasksService(session)
    service.client = Mock()
    service.client.create_task.return_value = {
        "id": "task-1",
        "title": "Follow up",
        "status": "needsAction",
    }

    payload = TasksCreateTaskInput(
        tasklist_id="list-1",
        task=TaskInput(title="Follow up", notes="Email customer"),
    )

    result = service.create_task(external_subject="user-1", input_data=payload)

    assert result["id"] == "task-1"
    assert result["tasklist_id"] == "list-1"
    service.client.create_task.assert_called_once()


def test_complete_task_marks_task_completed() -> None:
    session = Mock()
    service = TasksService(session)
    service.client = Mock()
    service.client.update_task.return_value = {
        "id": "task-2",
        "title": "Prepare report",
        "status": "completed",
        "completed": "2026-03-11T12:00:00Z",
    }

    payload = TasksCompleteTaskInput(
        tasklist_id="list-2",
        task_id="task-2",
        completed="2026-03-11T12:00:00Z",
    )

    result = service.complete_task(external_subject="user-1", input_data=payload)

    assert result["status"] == "completed"
    service.client.update_task.assert_called_once()
