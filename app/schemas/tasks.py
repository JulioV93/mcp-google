from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TaskListTitleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)


class TaskListRefInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasklist_id: str = Field(min_length=1)


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    notes: str | None = None
    due: str | None = None
    status: str | None = None


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

    task_id: str = Field(min_length=1)
    task: TaskInput


class TasksCompleteTaskInput(TaskListRefInput):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    completed: str | None = None


class TasksDeleteTaskInput(TaskListRefInput):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
