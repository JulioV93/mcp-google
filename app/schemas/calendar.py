from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CalendarEventDateTime(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_time: str | None = Field(default=None, alias="dateTime")
    date: str | None = None
    time_zone: str | None = Field(default=None, alias="timeZone")

    @model_validator(mode="after")
    def validate_presence(self) -> "CalendarEventDateTime":
        if not self.date_time and not self.date:
            raise ValueError("Either dateTime or date is required")
        return self


class CalendarEventReminderOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = Field(pattern="^(email|popup)$")
    minutes: int = Field(ge=0)


class CalendarEventReminders(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_default: bool | None = Field(default=None, alias="useDefault")
    overrides: list[CalendarEventReminderOverride] | None = None


class CalendarEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    summary: str
    description: str | None = None
    location: str | None = None
    color_id: str | None = Field(default=None, alias="colorId")
    start: CalendarEventDateTime
    end: CalendarEventDateTime
    recurrence: list[str] | None = None
    reminders: CalendarEventReminders | None = None


class CalendarListEventsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendar_id: str = "primary"
    time_min: str | None = None
    time_max: str | None = None
    max_results: int = 20
    page_token: str | None = None
    query: str | None = None


class CalendarGetEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendar_id: str = "primary"
    event_id: str


class CalendarCreateEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendar_id: str = "primary"
    event: CalendarEventInput


class CalendarUpdateEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendar_id: str = "primary"
    event_id: str
    event: CalendarEventInput


class CalendarDeleteEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendar_id: str = "primary"
    event_id: str
