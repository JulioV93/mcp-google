from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.google.tasks_client import TasksClient, TasksClientError
from app.schemas.tasks import (
    TasksCompleteTaskInput,
    TasksCreateTaskInput,
    TasksCreateTasklistInput,
    TasksDeleteTaskInput,
    TasksDeleteTasklistInput,
    TasksListTasklistsInput,
    TasksListTasksInput,
    TasksUpdateTaskInput,
    TasksUpdateTasklistInput,
)


class TasksServiceError(Exception):
    """Raised when Google Tasks operations fail."""


class TasksService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.client = TasksClient(session)

    def list_tasklists(
        self,
        *,
        external_subject: str,
        input_data: TasksListTasklistsInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.list_tasklists(
                external_subject=external_subject,
                tenant_id=tenant_id,
                max_results=input_data.max_results,
                page_token=input_data.page_token,
            )
        except TasksClientError as exc:
            raise TasksServiceError(str(exc)) from exc

        items = [_normalize_tasklist(item) for item in payload.get("items", [])]
        return {"items": items, "next_page_token": payload.get("nextPageToken")}

    def create_tasklist(
        self,
        *,
        external_subject: str,
        input_data: TasksCreateTasklistInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.create_tasklist(
                external_subject=external_subject,
                tenant_id=tenant_id,
                title=input_data.title,
            )
        except TasksClientError as exc:
            raise TasksServiceError(str(exc)) from exc
        return _normalize_tasklist(payload)

    def update_tasklist(
        self,
        *,
        external_subject: str,
        input_data: TasksUpdateTasklistInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.update_tasklist(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tasklist_id=input_data.tasklist_id,
                title=input_data.title,
            )
        except TasksClientError as exc:
            raise TasksServiceError(str(exc)) from exc
        return _normalize_tasklist(payload)

    def delete_tasklist(
        self,
        *,
        external_subject: str,
        input_data: TasksDeleteTasklistInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            self.client.delete_tasklist(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tasklist_id=input_data.tasklist_id,
            )
        except TasksClientError as exc:
            raise TasksServiceError(str(exc)) from exc
        return {"deleted": True, "tasklist_id": input_data.tasklist_id}

    def list_tasks(
        self,
        *,
        external_subject: str,
        input_data: TasksListTasksInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.list_tasks(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tasklist_id=input_data.tasklist_id,
                max_results=input_data.max_results,
                page_token=input_data.page_token,
                show_completed=input_data.show_completed,
                show_hidden=input_data.show_hidden,
            )
        except TasksClientError as exc:
            raise TasksServiceError(str(exc)) from exc

        items = [_normalize_task(item, input_data.tasklist_id) for item in payload.get("items", [])]
        return {"items": items, "next_page_token": payload.get("nextPageToken")}

    def create_task(
        self,
        *,
        external_subject: str,
        input_data: TasksCreateTaskInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.create_task(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tasklist_id=input_data.tasklist_id,
                task_body=input_data.task.model_dump(exclude_none=True),
            )
        except TasksClientError as exc:
            raise TasksServiceError(str(exc)) from exc
        return _normalize_task(payload, input_data.tasklist_id)

    def update_task(
        self,
        *,
        external_subject: str,
        input_data: TasksUpdateTaskInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.update_task(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tasklist_id=input_data.tasklist_id,
                task_id=input_data.task_id,
                task_body=input_data.task.model_dump(exclude_none=True),
            )
        except TasksClientError as exc:
            raise TasksServiceError(str(exc)) from exc
        return _normalize_task(payload, input_data.tasklist_id)

    def complete_task(
        self,
        *,
        external_subject: str,
        input_data: TasksCompleteTaskInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        completed = input_data.completed or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        try:
            payload = self.client.update_task(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tasklist_id=input_data.tasklist_id,
                task_id=input_data.task_id,
                task_body={"status": "completed", "completed": completed},
            )
        except TasksClientError as exc:
            raise TasksServiceError(str(exc)) from exc
        return _normalize_task(payload, input_data.tasklist_id)

    def delete_task(
        self,
        *,
        external_subject: str,
        input_data: TasksDeleteTaskInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            self.client.delete_task(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tasklist_id=input_data.tasklist_id,
                task_id=input_data.task_id,
            )
        except TasksClientError as exc:
            raise TasksServiceError(str(exc)) from exc
        return {
            "deleted": True,
            "tasklist_id": input_data.tasklist_id,
            "task_id": input_data.task_id,
        }


def _normalize_tasklist(payload: dict[str, object]) -> dict[str, object]:
    return {
        "id": payload.get("id"),
        "title": payload.get("title"),
        "updated": payload.get("updated"),
        "self_link": payload.get("selfLink"),
    }


def _normalize_task(payload: dict[str, object], tasklist_id: str) -> dict[str, object]:
    return {
        "id": payload.get("id"),
        "tasklist_id": tasklist_id,
        "title": payload.get("title"),
        "notes": payload.get("notes"),
        "status": payload.get("status"),
        "due": payload.get("due"),
        "completed": payload.get("completed"),
        "updated": payload.get("updated"),
        "self_link": payload.get("selfLink"),
    }
