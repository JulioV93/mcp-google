from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    status: str | None = Field(
        default=None, description="Google Tasks status such as needsAction or completed."
    )


class TaskPatchInput(TaskInput):
    title: str | None = Field(default=None, min_length=1)
    status: Literal["needsAction", "completed"] | None = None

    @field_validator("title", "notes", "status", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Null is only supported for due")
        return value

    @field_validator("due")
    @classmethod
    def validate_due(cls, value):
        if value is None:
            return value
        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})",
            value,
        ):
            raise ValueError("Expected RFC3339 with timezone")
        datetime.fromisoformat(value.upper())
        return value

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one task field is required")
        return self


class TasksListTasklistsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_results: int = Field(default=100, ge=1, le=100)
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

    max_results: int = Field(default=100, ge=1, le=100)
    page_token: str | None = None
    show_completed: bool = True
    show_hidden: bool = False


class TasksCreateTaskInput(TaskListRefInput):
    model_config = ConfigDict(extra="forbid")

    task: TaskInput


class TasksUpdateTaskInput(TaskListRefInput):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, description="Task ID within the selected task list.")
    task: TaskPatchInput


class TasksCompleteTaskInput(TaskListRefInput):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, description="Task ID to mark as completed.")
    completed: str | None = Field(
        default=None, description="Optional RFC3339 completion timestamp."
    )


class TasksDeleteTaskInput(TaskListRefInput):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, description="Task ID to delete.")


class TasksConfirmDeleteTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(min_length=1)
