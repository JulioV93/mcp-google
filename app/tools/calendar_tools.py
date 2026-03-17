from __future__ import annotations

from fastmcp import FastMCP

from app.schemas.calendar import (
    CalendarConfirmDeleteEventInput,
    CalendarCreateEventInput,
    CalendarDeleteEventInput,
    CalendarGetEventInput,
    CalendarListEventsInput,
    CalendarUpdateEventInput,
)
from app.services.calendar_service import CalendarService
from app.tools.common import run_tool


def register_calendar_tools(mcp: FastMCP) -> None:
    @mcp.tool
    def calendar_list_calendars() -> dict[str, object]:
        """List Google calendars for the current user.

        Use this first when the user did not specify which calendar to inspect or modify.
        Returns calendar IDs that can be reused in later Calendar calls.
        """
        return run_tool(
            tool_name="calendar_list_calendars",
            provider="google",
            resource_type="calendar",
            arguments={},
            operation=lambda session, context: CalendarService(session).list_calendars(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
            ),
        )

    @mcp.tool
    def calendar_list_events(
        calendar_id: str = "primary",
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 20,
        page_token: str | None = None,
        query: str | None = None,
    ) -> dict[str, object]:
        """List Google Calendar events for the current user.

        Use this to search by time range or query before calling get, update, or delete.
        Prefer this over `calendar_get_event` when you do not yet know the event ID.
        """
        payload = CalendarListEventsInput(
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
            page_token=page_token,
            query=query,
        )
        return run_tool(
            tool_name="calendar_list_events",
            provider="google",
            resource_type="calendar_event",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: CalendarService(session).list_events(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def calendar_get_event(calendar_id: str = "primary", event_id: str = "") -> dict[str, object]:
        """Get a Google Calendar event by ID.

        Use only when you already know the exact `event_id`.
        If the event identity is uncertain, use `calendar_list_events` first.
        """
        payload = CalendarGetEventInput(calendar_id=calendar_id, event_id=event_id)
        return run_tool(
            tool_name="calendar_get_event",
            provider="google",
            resource_type="calendar_event",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: CalendarService(session).get_event(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def calendar_create_event(calendar_id: str = "primary", event: dict[str, object] | None = None) -> dict[str, object]:
        """Create a Google Calendar event.

        Use for both one-off and recurring events.
        For recurring schedules, create a single event and set `event.recurrence` using Google Calendar RRULE syntax.
        Do not create multiple events to simulate repetition.

        Example recurrence values:
        - daily: ["RRULE:FREQ=DAILY"]
        - weekdays: ["RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"]
        """
        payload = CalendarCreateEventInput.model_validate({"calendar_id": calendar_id, "event": event or {}})
        return run_tool(
            tool_name="calendar_create_event",
            provider="google",
            resource_type="calendar_event",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: CalendarService(session).create_event(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def calendar_update_event(
        calendar_id: str = "primary",
        event_id: str = "",
        event: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Update a Google Calendar event.

        Use when the user wants to change an existing event and the `event_id` is known.
        If you need to locate the event first, use `calendar_list_events` before updating.
        """
        payload = CalendarUpdateEventInput.model_validate(
            {"calendar_id": calendar_id, "event_id": event_id, "event": event or {}}
        )
        return run_tool(
            tool_name="calendar_update_event",
            provider="google",
            resource_type="calendar_event",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: CalendarService(session).update_event(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def calendar_delete_event(calendar_id: str = "primary", event_id: str = "") -> dict[str, object]:
        """Prepare deletion of a Google Calendar event.

        This does not delete immediately. It returns an operation preview and `operation_id`.
        Use `calendar_confirm_delete_event` after review to execute the deletion.
        """
        payload = CalendarDeleteEventInput(calendar_id=calendar_id, event_id=event_id)
        return run_tool(
            tool_name="calendar_delete_event",
            provider="google",
            resource_type="calendar_event",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: CalendarService(session).delete_event(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def calendar_confirm_delete_event(operation_id: str) -> dict[str, object]:
        """Confirm deletion of a prepared Google Calendar event.

        Use only after reviewing the preview returned by `calendar_delete_event`.
        """
        payload = CalendarConfirmDeleteEventInput(operation_id=operation_id)
        return run_tool(
            tool_name="calendar_confirm_delete_event",
            provider="google",
            resource_type="calendar_event",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: CalendarService(session).confirm_delete_event(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )
