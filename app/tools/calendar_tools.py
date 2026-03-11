from __future__ import annotations

from fastmcp import FastMCP

from app.schemas.calendar import (
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
        """List Google calendars for the current user."""
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
        """List Google Calendar events for the current user."""
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
        """Get a Google Calendar event by ID."""
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
        """Create a Google Calendar event."""
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
        """Update a Google Calendar event."""
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
        """Delete a Google Calendar event."""
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
