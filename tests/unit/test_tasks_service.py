from __future__ import annotations

from typing import cast
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.base import Base
from app.schemas.tasks import (
    TaskInput,
    TasksCompleteTaskInput,
    TasksConfirmDeleteTaskInput,
    TasksConfirmDeleteTasklistInput,
    TasksCreateTaskInput,
    TasksDeleteTaskInput,
    TasksDeleteTasklistInput,
    TasksListTasklistsInput,
)
from app.services.tasks_service import TasksService


def create_test_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", future=True, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    return session_factory()


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
    items = cast(list[dict[str, object]], result["items"])

    assert result["next_page_token"] == "next-lists"
    assert result["resource_identity"] == {"type": "tasklist_collection"}
    assert items[0]["id"] == "list-1"


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
    assert result["resource_identity"] == {
        "type": "task",
        "tasklist_id": "list-1",
        "task_id": "task-1",
    }
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
    assert result["safety_level"] == "write"
    service.client.update_task.assert_called_once()


def test_delete_task_requires_confirmation_and_confirm_executes() -> None:
    session = create_test_session()
    service = TasksService(session, settings=Settings())
    service.client = Mock()
    service.client.get_task.return_value = {
        "id": "task-9",
        "title": "Remove me",
        "status": "needsAction",
    }

    prepare = service.delete_task(
        external_subject="user-1",
        input_data=TasksDeleteTaskInput(tasklist_id="list-1", task_id="task-9"),
    )

    assert prepare["requires_confirmation"] is True
    operation_id = cast(str, prepare["operation_id"])

    confirm = service.confirm_delete_task(
        external_subject="user-1",
        input_data=TasksConfirmDeleteTaskInput(operation_id=operation_id),
    )

    assert confirm["confirmed"] is True
    assert confirm["resource_identity"] == {
        "type": "task",
        "tasklist_id": "list-1",
        "task_id": "task-9",
    }
    service.client.delete_task.assert_called_once_with(
        external_subject="user-1",
        tenant_id=None,
        tasklist_id="list-1",
        task_id="task-9",
    )


def test_delete_tasklist_requires_confirmation_and_confirm_executes() -> None:
    session = create_test_session()
    service = TasksService(session, settings=Settings())
    service.client = Mock()
    service.client.get_tasklist.return_value = {
        "id": "list-9",
        "title": "Archive",
    }

    prepare = service.delete_tasklist(
        external_subject="user-1",
        input_data=TasksDeleteTasklistInput(tasklist_id="list-9"),
    )

    assert prepare["requires_confirmation"] is True
    operation_id = cast(str, prepare["operation_id"])

    confirm = service.confirm_delete_tasklist(
        external_subject="user-1",
        input_data=TasksConfirmDeleteTasklistInput(operation_id=operation_id),
    )

    assert confirm["confirmed"] is True
    assert confirm["resource_identity"] == {"type": "tasklist", "tasklist_id": "list-9"}
    service.client.delete_tasklist.assert_called_once_with(
        external_subject="user-1",
        tenant_id=None,
        tasklist_id="list-9",
    )
