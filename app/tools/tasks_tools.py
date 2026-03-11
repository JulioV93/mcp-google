from __future__ import annotations

from fastmcp import FastMCP

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
from app.services.tasks_service import TasksService
from app.tools.common import run_tool


def register_tasks_tools(mcp: FastMCP) -> None:
    @mcp.tool
    def tasks_list_tasklists(max_results: int = 100, page_token: str | None = None) -> dict[str, object]:
        """List Google task lists for the current user."""
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

    @mcp.tool
    def tasks_create_tasklist(title: str) -> dict[str, object]:
        """Create a Google task list."""
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

    @mcp.tool
    def tasks_update_tasklist(tasklist_id: str, title: str) -> dict[str, object]:
        """Update a Google task list."""
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

    @mcp.tool
    def tasks_delete_tasklist(tasklist_id: str) -> dict[str, object]:
        """Delete a Google task list."""
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

    @mcp.tool
    def tasks_list_tasks(
        tasklist_id: str,
        max_results: int = 100,
        page_token: str | None = None,
        show_completed: bool = True,
        show_hidden: bool = False,
    ) -> dict[str, object]:
        """List Google tasks from a task list."""
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

    @mcp.tool
    def tasks_create_task(tasklist_id: str, task: dict[str, object] | None = None) -> dict[str, object]:
        """Create a Google task."""
        payload = TasksCreateTaskInput.model_validate({"tasklist_id": tasklist_id, "task": task or {}})
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

    @mcp.tool
    def tasks_update_task(tasklist_id: str, task_id: str, task: dict[str, object] | None = None) -> dict[str, object]:
        """Update a Google task."""
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

    @mcp.tool
    def tasks_complete_task(tasklist_id: str, task_id: str, completed: str | None = None) -> dict[str, object]:
        """Mark a Google task as completed."""
        payload = TasksCompleteTaskInput(tasklist_id=tasklist_id, task_id=task_id, completed=completed)
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

    @mcp.tool
    def tasks_delete_task(tasklist_id: str, task_id: str) -> dict[str, object]:
        """Delete a Google task."""
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
