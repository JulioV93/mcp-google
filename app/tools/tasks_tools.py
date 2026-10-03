from __future__ import annotations

from fastmcp import FastMCP

from app.schemas.tasks import (
    TasksCompleteTaskInput,
    TasksConfirmDeleteTaskInput,
    TasksConfirmDeleteTasklistInput,
    TasksCreateTaskInput,
    TasksCreateTasklistInput,
    TasksDeleteTaskInput,
    TasksDeleteTasklistInput,
    TasksListTasklistsInput,
    TasksListTasksInput,
    TasksUpdateTaskInput,
    TasksUpdateTasklistInput,
)
from app.security.tool_policy import tool_annotations
from app.services.tasks_service import TasksService
from app.tools.common import run_tool


def register_tasks_tools(mcp: FastMCP) -> None:
    @mcp.tool(annotations=tool_annotations("tasks_list_tasklists"))
    def tasks_list_tasklists(
        max_results: int = 100, page_token: str | None = None
    ) -> dict[str, object]:
        """List Google task lists for the current user.

        Use this first when the user names a list but you do not yet know its `tasklist_id`.
        """
        payload = TasksListTasklistsInput(max_results=max_results, page_token=page_token)
        return run_tool(
            tool_name="tasks_list_tasklists",
            provider="google",
            resource_type="tasklist",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: TasksService(session).list_tasklists(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool(annotations=tool_annotations("tasks_create_tasklist"))
    def tasks_create_tasklist(title: str) -> dict[str, object]:
        """Create a Google task list.

        Use when the user wants a new task container such as a project list or routine list.
        """
        payload = TasksCreateTasklistInput(title=title)
        return run_tool(
            tool_name="tasks_create_tasklist",
            provider="google",
            resource_type="tasklist",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: TasksService(session).create_tasklist(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool(annotations=tool_annotations("tasks_update_tasklist"))
    def tasks_update_tasklist(tasklist_id: str, title: str) -> dict[str, object]:
        """Update a Google task list.

        Use when the user wants to rename an existing task list and you already know its ID.
        """
        payload = TasksUpdateTasklistInput(tasklist_id=tasklist_id, title=title)
        return run_tool(
            tool_name="tasks_update_tasklist",
            provider="google",
            resource_type="tasklist",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: TasksService(session).update_tasklist(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool(annotations=tool_annotations("tasks_delete_tasklist"))
    def tasks_delete_tasklist(tasklist_id: str) -> dict[str, object]:
        """Prepare deletion of a Google task list.

        This does not delete immediately. It returns an operation preview and `operation_id`.
        Use `tasks_confirm_delete_tasklist` after review to execute the deletion.
        """
        payload = TasksDeleteTasklistInput(tasklist_id=tasklist_id)
        return run_tool(
            tool_name="tasks_delete_tasklist",
            provider="google",
            resource_type="tasklist",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: TasksService(session).delete_tasklist(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool(annotations=tool_annotations("tasks_confirm_delete_tasklist"))
    def tasks_confirm_delete_tasklist(operation_id: str) -> dict[str, object]:
        """Confirm deletion of a prepared Google task list."""
        payload = TasksConfirmDeleteTasklistInput(operation_id=operation_id)
        return run_tool(
            tool_name="tasks_confirm_delete_tasklist",
            provider="google",
            resource_type="tasklist",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: TasksService(session).confirm_delete_tasklist(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool(annotations=tool_annotations("tasks_list_tasks"))
    def tasks_list_tasks(
        tasklist_id: str,
        max_results: int = 100,
        page_token: str | None = None,
        show_completed: bool = True,
        show_hidden: bool = False,
    ) -> dict[str, object]:
        """List Google tasks from a task list.

        Use before update, complete, or delete when you need to locate a task ID.

        Example payload:
        ```json
        {
          "tasklist_id": "abc",
          "max_results": 20,
          "show_completed": false
        }
        ```
        """
        payload = TasksListTasksInput(
            tasklist_id=tasklist_id,
            max_results=max_results,
            page_token=page_token,
            show_completed=show_completed,
            show_hidden=show_hidden,
        )
        return run_tool(
            tool_name="tasks_list_tasks",
            provider="google",
            resource_type="task",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: TasksService(session).list_tasks(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool(annotations=tool_annotations("tasks_create_task"))
    def tasks_create_task(
        tasklist_id: str, task: dict[str, object] | None = None
    ) -> dict[str, object]:
        """Create a Google task.

        Use for new tasks with title, notes, or due date.

        Example payload:
        ```json
        {
          "tasklist_id": "abc",
          "task": {
            "title": "Mi tarea",
            "due": "2026-04-30T00:00:00.000Z"
          }
        }
        ```
        """
        payload = TasksCreateTaskInput.model_validate(
            {"tasklist_id": tasklist_id, "task": task or {}}
        )
        return run_tool(
            tool_name="tasks_create_task",
            provider="google",
            resource_type="task",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: TasksService(session).create_task(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool(annotations=tool_annotations("tasks_update_task"))
    def tasks_update_task(
        tasklist_id: str, task_id: str, task: dict[str, object] | None = None
    ) -> dict[str, object]:
        """Update a Google task.

        Use for changing task title, notes, or due date.
        If the user wants to mark a task done, prefer `tasks_complete_task`.

        Example payload:
        ```json
        {
          "tasklist_id": "abc",
          "task_id": "task-123",
          "task": {
            "title": "Mi tarea actualizada",
            "due": "2026-05-02T18:00:00.000Z"
          }
        }
        ```
        """
        payload = TasksUpdateTaskInput.model_validate(
            {"tasklist_id": tasklist_id, "task_id": task_id, "task": task or {}}
        )
        return run_tool(
            tool_name="tasks_update_task",
            provider="google",
            resource_type="task",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: TasksService(session).update_task(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool(annotations=tool_annotations("tasks_complete_task"))
    def tasks_complete_task(
        tasklist_id: str, task_id: str, completed: str | None = None
    ) -> dict[str, object]:
        """Mark a Google task as completed.

        Prefer this over `tasks_update_task` when the user intent is to finish or close a task.

        Example payload:
        ```json
        {
          "tasklist_id": "abc",
          "task_id": "task-123"
        }
        ```
        """
        payload = TasksCompleteTaskInput(
            tasklist_id=tasklist_id, task_id=task_id, completed=completed
        )
        return run_tool(
            tool_name="tasks_complete_task",
            provider="google",
            resource_type="task",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: TasksService(session).complete_task(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool(annotations=tool_annotations("tasks_delete_task"))
    def tasks_delete_task(tasklist_id: str, task_id: str) -> dict[str, object]:
        """Prepare deletion of a Google task.

        This does not delete immediately. It returns an operation preview and `operation_id`.
        Use `tasks_confirm_delete_task` after review to execute the deletion.

        Example payload:
        ```json
        {
          "tasklist_id": "abc",
          "task_id": "task-123"
        }
        ```
        """
        payload = TasksDeleteTaskInput(tasklist_id=tasklist_id, task_id=task_id)
        return run_tool(
            tool_name="tasks_delete_task",
            provider="google",
            resource_type="task",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: TasksService(session).delete_task(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool(annotations=tool_annotations("tasks_confirm_delete_task"))
    def tasks_confirm_delete_task(operation_id: str) -> dict[str, object]:
        """Confirm deletion of a prepared Google task."""
        payload = TasksConfirmDeleteTaskInput(operation_id=operation_id)
        return run_tool(
            tool_name="tasks_confirm_delete_task",
            provider="google",
            resource_type="task",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: TasksService(session).confirm_delete_task(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )
