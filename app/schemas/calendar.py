from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CalendarEventDateTime(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_time: str | None = Field(
        default=None,
        alias="dateTime",
        description="RFC3339 date-time for timed events.",
    )
    date: str | None = Field(default=None, description="All-day event date in YYYY-MM-DD format.")
    time_zone: str | None = Field(
        default=None,
        alias="timeZone",
        description="IANA timezone such as America/Santiago.",
    )

    @model_validator(mode="after")
    def validate_presence(self) -> CalendarEventDateTime:
        if not self.date_time and not self.date:
            raise ValueError("Either dateTime or date is required")
        return self


class CalendarEventReminderOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = Field(pattern="^(email|popup)$", description="Reminder delivery method.")
    minutes: int = Field(
        ge=0, description="Minutes before the event when the reminder should fire."
    )


class CalendarEventReminders(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_default: bool | None = Field(
        default=None,
        alias="useDefault",
        description="Whether to use Google Calendar default reminders.",
    )
    overrides: list[CalendarEventReminderOverride] | None = Field(
        default=None,
        description="Explicit reminder overrides when not using default reminders.",
    )


class CalendarEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    summary: str = Field(description="Human-readable event title.")
    description: str | None = Field(default=None, description="Optional event body or notes.")
    location: str | None = Field(default=None, description="Optional event location.")
    color_id: str | None = Field(
        default=None, alias="colorId", description="Google Calendar color ID."
    )
    start: CalendarEventDateTime
    end: CalendarEventDateTime
    recurrence: list[str] | None = Field(
        default=None,
        description="Google Calendar RRULE values for recurring events. Use one event plus recurrence instead of creating many duplicate events.",
    )
    reminders: CalendarEventReminders | None = Field(
        default=None,
        description="Optional reminder configuration for the event.",
    )


class CalendarListEventsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendar_id: str = "primary"
    time_min: str | None = None
    time_max: str | None = None
    max_results: int = Field(default=20, ge=1, le=2500)
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


class CalendarConfirmDeleteEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
