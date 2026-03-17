from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import Mock

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import PendingGoogleOperation
from app.db.repositories.pending_google_operations import PendingGoogleOperationRepository
from app.errors import AppError
from app.google.tasks_client import TasksClient
from app.schemas.tasks import (
    TasksConfirmDeleteTaskInput,
    TasksConfirmDeleteTasklistInput,
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


class TasksService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.client = TasksClient(session)
        self.connections = ConnectionService(session)
        self.pending_operations = PendingGoogleOperationRepository(session)

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
        except AppError:
            raise

        items = [_normalize_tasklist(item) for item in cast(list[dict[str, object]], payload.get("items") or [])]
        next_page_token_raw = payload.get("nextPageToken")
        next_page_token = next_page_token_raw if isinstance(next_page_token_raw, str) else None
        return enrich_collection(
            items=items,
            next_page_token=next_page_token,
            resource_type="tasklist_collection",
            human_summary=f"Found {len(items)} task list(s).",
            next_suggested_actions=["tasks_create_tasklist", "tasks_list_tasks", "tasks_update_tasklist"],
            safety_level="read",
        )

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
        except AppError:
            raise
        normalized = _normalize_tasklist(payload)
        return enrich_resource(
            normalized,
            resource_type="tasklist",
            tasklist_id=normalized.get("id"),
            human_summary=f"Created task list '{normalized.get('title') or normalized.get('id')}'.",
            next_suggested_actions=["tasks_list_tasks", "tasks_update_tasklist", "tasks_delete_tasklist"],
            safety_level="write",
        )

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
        except AppError:
            raise
        normalized = _normalize_tasklist(payload)
        return enrich_resource(
            normalized,
            resource_type="tasklist",
            tasklist_id=normalized.get("id"),
            human_summary=f"Updated task list '{normalized.get('title') or normalized.get('id')}'.",
            next_suggested_actions=["tasks_list_tasks", "tasks_create_task", "tasks_delete_tasklist"],
            safety_level="write",
        )

    def prepare_delete_tasklist(
        self,
        *,
        external_subject: str,
        input_data: TasksDeleteTasklistInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        metadata = _normalize_tasklist(
            self.client.get_tasklist(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tasklist_id=input_data.tasklist_id,
            )
        )
        record = self._create_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type="tasks_delete_tasklist",
            resource_type="tasklist",
            resource_id=input_data.tasklist_id,
            resource_name=_nullable_str(metadata.get("title")),
            payload_normalized={"tasklist_id": input_data.tasklist_id},
        )
        return _preview_from_record(
            record,
            risk_level="high",
            summary={
                "action": "delete_tasklist",
                "tasklist_id": input_data.tasklist_id,
                "title": metadata.get("title"),
            },
        )

    def delete_tasklist(
        self,
        *,
        external_subject: str,
        input_data: TasksDeleteTasklistInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        return self.prepare_delete_tasklist(
            external_subject=external_subject,
            input_data=input_data,
            tenant_id=tenant_id,
        )

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
        except AppError:
            raise

        items = [
            _normalize_task(item, input_data.tasklist_id)
            for item in cast(list[dict[str, object]], payload.get("items") or [])
        ]
        next_page_token_raw = payload.get("nextPageToken")
        next_page_token = next_page_token_raw if isinstance(next_page_token_raw, str) else None
        return enrich_collection(
            items=items,
            next_page_token=next_page_token,
            resource_type="task_collection",
            tasklist_id=input_data.tasklist_id,
            human_summary=f"Found {len(items)} task(s) in task list '{input_data.tasklist_id}'.",
            next_suggested_actions=["tasks_create_task", "tasks_update_task", "tasks_complete_task"],
            safety_level="read",
        )

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
        except AppError:
            raise
        normalized = _normalize_task(payload, input_data.tasklist_id)
        return enrich_resource(
            normalized,
            resource_type="task",
            tasklist_id=input_data.tasklist_id,
            task_id=normalized.get("id"),
            human_summary=f"Created task '{normalized.get('title') or normalized.get('id')}'.",
            next_suggested_actions=["tasks_update_task", "tasks_complete_task", "tasks_delete_task"],
            safety_level="write",
        )

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
        except AppError:
            raise
        normalized = _normalize_task(payload, input_data.tasklist_id)
        return enrich_resource(
            normalized,
            resource_type="task",
            tasklist_id=input_data.tasklist_id,
            task_id=normalized.get("id"),
            human_summary=f"Updated task '{normalized.get('title') or normalized.get('id')}'.",
            next_suggested_actions=["tasks_complete_task", "tasks_delete_task", "tasks_list_tasks"],
            safety_level="write",
        )

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
        except AppError:
            raise
        normalized = _normalize_task(payload, input_data.tasklist_id)
        return enrich_resource(
            normalized,
            resource_type="task",
            tasklist_id=input_data.tasklist_id,
            task_id=normalized.get("id"),
            human_summary=f"Completed task '{normalized.get('title') or normalized.get('id')}'.",
            next_suggested_actions=["tasks_list_tasks", "tasks_update_task", "tasks_delete_task"],
            safety_level="write",
        )

    def prepare_delete_task(
        self,
        *,
        external_subject: str,
        input_data: TasksDeleteTaskInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        metadata = _normalize_task(
            self.client.get_task(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tasklist_id=input_data.tasklist_id,
                task_id=input_data.task_id,
            ),
            input_data.tasklist_id,
        )
        record = self._create_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type="tasks_delete_task",
            resource_type="task",
            resource_id=input_data.task_id,
            resource_name=_nullable_str(metadata.get("title")),
            payload_normalized={"tasklist_id": input_data.tasklist_id, "task_id": input_data.task_id},
        )
        return _preview_from_record(
            record,
            risk_level="high",
            summary={
                "action": "delete_task",
                "tasklist_id": input_data.tasklist_id,
                "task_id": input_data.task_id,
                "title": metadata.get("title"),
                "status": metadata.get("status"),
            },
        )

    def delete_task(
        self,
        *,
        external_subject: str,
        input_data: TasksDeleteTaskInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        return self.prepare_delete_task(
            external_subject=external_subject,
            input_data=input_data,
            tenant_id=tenant_id,
        )

    def confirm_delete_tasklist(
        self,
        *,
        external_subject: str,
        input_data: TasksConfirmDeleteTasklistInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        record = self._get_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=input_data.operation_id,
            expected_operation_type="tasks_delete_tasklist",
        )
        payload = record.payload_normalized
        tasklist_id = _as_str(payload.get("tasklist_id"))
        self.client.delete_tasklist(
            external_subject=external_subject,
            tenant_id=tenant_id,
            tasklist_id=tasklist_id,
        )
        self.pending_operations.mark_confirmed(record)
        self.session.commit()
        return enrich_resource(
            {
                "operation_id": input_data.operation_id,
                "confirmed": True,
                "deleted": True,
                "tasklist_id": tasklist_id,
            },
            resource_type="tasklist",
            tasklist_id=tasklist_id,
            human_summary=f"Deleted task list '{record.resource_name or tasklist_id}'.",
            next_suggested_actions=["tasks_list_tasklists", "tasks_create_tasklist"],
            safety_level="destructive",
        )

    def confirm_delete_task(
        self,
        *,
        external_subject: str,
        input_data: TasksConfirmDeleteTaskInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        record = self._get_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=input_data.operation_id,
            expected_operation_type="tasks_delete_task",
        )
        payload = record.payload_normalized
        tasklist_id = _as_str(payload.get("tasklist_id"))
        task_id = _as_str(payload.get("task_id"))
        self.client.delete_task(
            external_subject=external_subject,
            tenant_id=tenant_id,
            tasklist_id=tasklist_id,
            task_id=task_id,
        )
        self.pending_operations.mark_confirmed(record)
        self.session.commit()
        return enrich_resource(
            {
                "operation_id": input_data.operation_id,
                "confirmed": True,
                "deleted": True,
                "tasklist_id": tasklist_id,
                "task_id": task_id,
            },
            resource_type="task",
            tasklist_id=tasklist_id,
            task_id=task_id,
            human_summary=f"Deleted task '{record.resource_name or task_id}'.",
            next_suggested_actions=["tasks_list_tasks", "tasks_create_task"],
            safety_level="destructive",
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


def _nullable_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
