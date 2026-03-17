from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TaskListTitleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, description="Visible task list or task title.")


class TaskListRefInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasklist_id: str = Field(min_length=1, description="Google Tasks task list ID.")


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, description="Human-readable task title.")
    notes: str | None = Field(default=None, description="Optional task notes.")
    due: str | None = Field(default=None, description="Optional RFC3339 due date-time.")
    status: str | None = Field(default=None, description="Google Tasks status such as needsAction or completed.")


class TasksListTasklistsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_results: int = 100
    page_token: str | None = None


class TasksCreateTasklistInput(TaskListTitleInput):
    pass


class TasksUpdateTasklistInput(TaskListRefInput, TaskListTitleInput):
    pass


class TasksDeleteTasklistInput(TaskListRefInput):
    pass


class TasksConfirmDeleteTasklistInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(min_length=1)


class TasksListTasksInput(TaskListRefInput):
    model_config = ConfigDict(extra="forbid")

    max_results: int = 100
    page_token: str | None = None
    show_completed: bool = True
    show_hidden: bool = False


class TasksCreateTaskInput(TaskListRefInput):
    model_config = ConfigDict(extra="forbid")

    task: TaskInput


class TasksUpdateTaskInput(TaskListRefInput):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, description="Task ID within the selected task list.")
    task: TaskInput


class TasksCompleteTaskInput(TaskListRefInput):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, description="Task ID to mark as completed.")
    completed: str | None = Field(default=None, description="Optional RFC3339 completion timestamp.")


class TasksDeleteTaskInput(TaskListRefInput):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, description="Task ID to delete.")


class TasksConfirmDeleteTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(min_length=1)
