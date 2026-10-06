from __future__ import annotations

from fastmcp import FastMCP

OVERVIEW_URI = "google-mcp://guide/overview"
SAFETY_URI = "google-mcp://guide/safety"
ERRORS_URI = "google-mcp://guide/error-handling"
CALENDAR_URI = "google-mcp://guide/calendar"
TASKS_URI = "google-mcp://guide/tasks"
GMAIL_URI = "google-mcp://guide/gmail"
DRIVE_URI = "google-mcp://guide/drive"
CALENDAR_EXAMPLES_URI = "google-mcp://examples/calendar"
TASKS_EXAMPLES_URI = "google-mcp://examples/tasks"
GMAIL_EXAMPLES_URI = "google-mcp://examples/gmail"
DRIVE_EXAMPLES_URI = "google-mcp://examples/drive"
CALENDAR_CONFIRM_EXAMPLES_URI = "google-mcp://examples/calendar/confirm-delete"
TASKS_CONFIRM_EXAMPLES_URI = "google-mcp://examples/tasks/confirm-delete"
GMAIL_CONFIRM_EXAMPLES_URI = "google-mcp://examples/gmail/confirm-send"
DRIVE_CONFIRM_EXAMPLES_URI = "google-mcp://examples/drive/confirm-operations"


def overview_guide() -> str:
    return """Google MCP overview

Domains:
- Calendar: calendars and events
- Tasks: task lists and tasks
- Gmail: messages, threads, drafts, and send
- Drive: files, folders, permissions, and guarded mutations

Operating model:
- use list or search tools before get, update, or delete when you do not have an ID
- prefer the least destructive tool that satisfies the intent
- for risky Drive mutations, use prepare tools first and confirm only after review
- read tool descriptions because they contain decision rules and examples
- inspect auth_get_permissions when access is unclear
- in server_policy mode, permissions live on the server and writes use the same JWT
"""


def safety_guide() -> str:
    return """Google MCP safety guide

Safety principles:
- prefer read operations before write operations
- never simulate recurring calendar events by creating many separate events
- use Gmail drafts when the user wants review before sending
- treat Gmail trash as a mutation even though it is reversible
- search Drive before mutating when the user did not provide a file ID
- Drive prepare_* tools do not execute mutations; confirm_* tools do
- server_policy writes require persistent read_write access for the authenticated identity
- only legacy jwt_claims mode uses the signed approved_tools claim
- a clear user request may authorize the full prepare/confirm workflow
- requires_confirmation means a technical call; use confirmation_tool and confirmation_arguments
- clarify ambiguity or a scope change in the preview before confirming
- respect the agent client's own approval policy
- preparation is not proof of human consent
- never repeat an operation with an uncertain external outcome

High-risk operations:
- calendar_delete_event
- tasks_delete_tasklist
- tasks_delete_task
- gmail_send_email
- gmail_delete_message
- all Drive confirm_* mutation tools

Good defaults:
- Calendar: list calendars if the user did not name one
- Tasks: list tasklists if the tasklist is unknown
- Gmail: list messages or threads before operating on a message ID
- Drive: search files before move, share, save, or delete when file identity is uncertain
"""


def error_handling_guide() -> str:
    return """Google MCP error handling guide

Validation failures include safe field paths and error types in metadata.validation_errors.
Correct the payload before retrying. Uncertain writes are never automatically retried.
An uncertain error may include metadata.diagnostic_id for server-log correlation.

Structured errors include:
- error
- detail
- retryable
- category
- optional metadata
- optional hint
- optional expected_fields
- optional example_payload
- optional recommended_tool

How to react:
- validation_error: fix the payload, follow hint or example_payload, retry once
- google_consent_required: reconnect Google auth, then retry
- insufficient_scope: reconnect with broader scopes, do not retry unchanged
- resource_not_found: refresh list or search results before retrying
- provider_temporary_error: retry reads with backoff
- google_operation_outcome_unknown: inspect the Google resource; never repeat operation_id or automatically prepare another write
- auth_provider_unavailable: wait for the JWT key provider; do not bypass authentication
- internal_error: stop and report the server problem
- permission_denied: ask the server administrator to enable access; do not renew JWT or ask for another chat approval
- approval_required: legacy jwt_claims authorization only; ask the token issuer to authorize the tool

Domain-specific recovery:
- Calendar recurrence problems: use event.recurrence with RRULE
- Tasks completion intent: prefer tasks_complete_task over generic update
- Gmail uncertainty: prefer draft creation when send intent is not explicit
- Drive native Google files: export instead of download or inline save
"""


def calendar_guide() -> str:
    return """Google Calendar guide

Primary tools:
- calendar_list_calendars
- calendar_list_events
- calendar_get_event
- calendar_create_event
- calendar_update_event
- calendar_delete_event

Decision rules:
- use calendar_list_calendars when the calendar is not specified
- use calendar_list_events to search by time range or text before get/update/delete
- use calendar_get_event only when you already have event_id
- use calendar_create_event for both one-off and recurring events
- for recurring events, create one event and set event.recurrence with RRULE
- Do not create multiple events to simulate a recurring schedule
- use calendar_update_event to change an existing event by ID; send only changed fields
- omitted event fields remain unchanged; summary/start/end are not mandatory for updates
- null event fields are invalid; clear description/location with "" and recurrence with []
- arrays in event updates replace the existing arrays
- use calendar_delete_event only when the user explicitly wants removal

Common recurrence mappings:
- daily -> [\"RRULE:FREQ=DAILY\"]
- weekly -> [\"RRULE:FREQ=WEEKLY\"]
- weekdays -> [\"RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR\"]
- each monday -> [\"RRULE:FREQ=WEEKLY;BYDAY=MO\"]
"""


def tasks_guide() -> str:
    return """Google Tasks guide

Primary tools:
- tasks_list_tasklists
- tasks_create_tasklist
- tasks_update_tasklist
- tasks_delete_tasklist
- tasks_list_tasks
- tasks_create_task
- tasks_update_task
- tasks_complete_task
- tasks_delete_task

Decision rules:
- list tasklists first if the user did not identify the task list
- use tasks_create_task for new tasks with title, notes, or due date
- use tasks_update_task for title, notes, or due date changes; send only changed fields
- title is required for creation, not for updates; an update must contain at least one field
- omitted fields remain unchanged; send due: null to remove a due date
- dates must be RFC3339 with timezone; Google stores the date, not the time
- clear notes with ""; null title/notes/status and unknown fields are invalid
- use tasks_complete_task when the intent is to finish or mark done
- use tasks_delete_task only for explicit removal
- use tasks_delete_tasklist only for explicit removal of the entire list
- after an explicit removal request, review the preview and execute its confirmation_tool with confirmation_arguments
"""


def gmail_guide() -> str:
    return """Gmail guide

Primary tools:
- gmail_list_messages
- gmail_get_message
- gmail_list_threads
- gmail_create_draft
- gmail_update_draft
- gmail_delete_draft
- gmail_send_email
- gmail_delete_message

Decision rules:
- use gmail_list_messages to find candidate message IDs
- use gmail_list_threads when conversation context matters more than a single message
- use gmail_get_message only after locating the message ID
- use gmail_create_draft when the user wants review before sending
- use gmail_send_email to prepare a send preview, then confirm with gmail_confirm_send_email
- gmail_delete_message moves the message to trash; it is not a permanent delete tool
"""


def drive_guide() -> str:
    return """Google Drive guide

Primary read tools:
- drive_list_files
- drive_search_files
- drive_find_folder_by_name
- drive_find_file_by_name
- drive_search_files_advanced
- drive_get_file
- drive_list_permissions
- drive_download_file
- drive_export_file

Primary mutation tools:
- drive_create_folder
- drive_create_google_doc
- drive_create_google_sheet
- drive_create_google_slide
- drive_create_shortcut
- drive_update_metadata
- drive_move_file
- drive_prepare_upload / drive_confirm_upload
- drive_prepare_upload_markdown / drive_confirm_upload
- drive_prepare_save_file / drive_confirm_save_file
- drive_prepare_write_google_doc / drive_confirm_write_google_doc
- drive_prepare_write_google_sheet / drive_confirm_write_google_sheet
- drive_prepare_delete_file / drive_confirm_delete_file
- drive_prepare_share_file / drive_confirm_share_file
- drive_prepare_revoke_permission / drive_confirm_revoke_permission

Decision rules:
- search before mutate when file identity is uncertain
- prefer `drive_find_folder_by_name` or `drive_find_file_by_name` when the user gives a natural-language name but not a file ID
- use `file_type` values like `folder`, `doc`, `sheet`, or `pdf` instead of forcing small agents to remember Drive mime types
- smart find tools return `status`, `best_match`, `matches_count`, `match_type`, and `score` so agents can decide whether to proceed or clarify
- create native Docs, Sheets, and Slides with the dedicated drive_create_google_* tools
- write text into native Docs with drive_prepare_write_google_doc then drive_confirm_write_google_doc
- write tabular values into native Sheets with drive_prepare_write_google_sheet then drive_confirm_write_google_sheet
- set `create_sheet_if_missing=true` when the user wants a brand new tab/worksheet inside an existing spreadsheet
- upload `.md` or other text files directly with drive_prepare_upload using `content_text` and `mime_type: text/markdown`
- download non-native files with drive_download_file
- export Google Docs, Sheets, and Slides with drive_export_file
- prepare_* tools create a preview and operation_id but do not mutate
- confirm_* tools execute the prepared mutation
"""


def calendar_examples() -> str:
    return """Calendar examples

Create a simple event:
{
  "calendar_id": "primary",
  "event": {
    "summary": "1:1 Sync",
    "start": {"dateTime": "2026-03-20T15:00:00-03:00"},
    "end": {"dateTime": "2026-03-20T15:30:00-03:00"}
  }
}

Update only an existing event description:
{
  "calendar_id": "primary",
  "event_id": "evt-123",
  "event": {"description": "Updated notes"}
}

Create a recurring weekday event:
{
  "calendar_id": "primary",
  "event": {
    "summary": "[TRADING] Practica y journal",
    "start": {"dateTime": "2026-03-17T07:30:00-03:00", "timeZone": "America/Santiago"},
    "end": {"dateTime": "2026-03-17T08:15:00-03:00", "timeZone": "America/Santiago"},
    "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"]
  }
}
"""


def calendar_confirm_examples() -> str:
    return """Calendar confirm-flow example

Prepare delete:
{
  "calendar_id": "primary",
  "event_id": "evt-123"
}

Confirm delete:
{
  "operation_id": "<operation_id_from_calendar_delete_event>"
}
"""


def tasks_examples() -> str:
    return """Tasks examples

List tasks from a known list:
{
  "tasklist_id": "abc",
  "max_results": 20,
  "show_completed": false
}

Create a task:
{
  "tasklist_id": "abc",
  "task": {
    "title": "Mi tarea",
    "due": "2026-04-30T00:00:00.000Z"
  }
}

Update only a task date (title is not required):
{
  "tasklist_id": "abc",
  "task_id": "task-123",
  "task": {
    "due": "2026-05-02T00:00:00.000Z"
  }
}

Remove an existing task due date:
{
  "tasklist_id": "abc",
  "task_id": "task-123",
  "task": {"due": null}
}

Complete a task:
{
  "tasklist_id": "abc",
  "task_id": "task-123"
}
"""


def tasks_confirm_examples() -> str:
    return """Tasks confirm-flow examples

Prepare task delete:
{
  "tasklist_id": "tasklist-123",
  "task_id": "task-456"
}

Confirm task delete:
{
  "operation_id": "<operation_id_from_tasks_delete_task>"
}

Prepare tasklist delete:
{
  "tasklist_id": "tasklist-123"
}

Confirm tasklist delete:
{
  "operation_id": "<operation_id_from_tasks_delete_tasklist>"
}
"""


def gmail_examples() -> str:
    return """Gmail examples

List messages:
{
  "query": "from:person@example.com newer_than:7d",
  "max_results": 10
}

Create a draft:
{
  "message": {
    "to": ["person@example.com"],
    "subject": "Seguimiento",
    "body_text": "Hola, te comparto el resumen."
  }
}

Send immediately:
{
  "message": {
    "to": ["person@example.com"],
    "subject": "Confirmacion",
    "body_text": "Queda confirmado para manana."
  }
}
"""


def gmail_confirm_examples() -> str:
    return """Gmail confirm-flow example

Prepare send:
{
  "message": {
    "to": ["person@example.com"],
    "subject": "Confirmacion",
    "body_text": "Queda confirmado para manana."
  }
}

Confirm send:
{
  "operation_id": "<operation_id_from_gmail_send_email>"
}
"""


def drive_examples() -> str:
    return """Drive examples

Search before mutation:
{
  "name": "roadmap",
  "mime_type": "application/pdf"
}

Find a folder by name:
{
  "name": "Sistema de Notas de Proyectos",
  "exact": true,
  "normalized": true,
  "include_trashed": false,
  "max_results": 10
}

Find a file by name and high-level type:
{
  "name": "Plan 2026",
  "file_type": "doc",
  "exact": false,
  "normalized": true,
  "include_trashed": false,
  "max_results": 20
}

Advanced Drive search:
{
  "terms": ["Sistema", "Notas", "Proyectos"],
  "mime_types": ["application/vnd.google-apps.folder"],
  "match_mode": "all_terms",
  "normalized": true,
  "fuzzy": true,
  "include_trashed": false,
  "page_size": 20
}

Export a Google Doc as PDF:
{
  "file_id": "file-123",
  "export_mime_type": "application/pdf"
}

Prepare writing a Google Doc:
{
  "file_id": "file-123",
  "content_text": "Resumen semanal\n- foco\n- metricas",
  "mode": "replace"
}

Prepare writing a Google Sheet:
{
  "file_id": "file-123",
  "sheet_name": "Resumen",
  "create_sheet_if_missing": true,
  "start_cell": "A1",
  "values": [
    ["Fecha", "PnL"],
    ["2026-03-20", 125.5]
  ]
}

Prepare share:
{
  "file_id": "file-123",
  "permission": {
    "type": "user",
    "role": "reader",
    "email_address": "person@example.com"
  }
}
"""


def drive_confirm_examples() -> str:
    return """Drive confirm-flow examples

Prepare upload:
{
  "name": "notes.txt",
  "content": {
    "content_text": "hello",
    "mime_type": "text/plain"
  }
}

Confirm upload:
{
  "operation_id": "<operation_id_from_drive_prepare_upload>"
}

Prepare share:
{
  "file_id": "file-123",
  "permission": {
    "type": "user",
    "role": "reader",
    "email_address": "person@example.com"
  }
}

Confirm share:
{
  "operation_id": "<operation_id_from_drive_prepare_share_file>"
}
"""


def calendar_prompt_text() -> str:
    return "Use one calendar event plus event.recurrence for repeated schedules. List or search before mutating when event_id is unknown."


def tasks_prompt_text() -> str:
    return "List tasklists first when the destination list is unknown. Use tasks_complete_task for completion intent instead of generic update."


def gmail_prompt_text() -> str:
    return "Prefer drafts when the user wants review or when send intent is ambiguous. Use list_messages or list_threads before operating on message IDs."


def drive_prompt_text() -> str:
    return "Search before mutating unknown files. Use export for Google-native files. Prepare tools preview risky mutations and confirm tools execute them."


def register_guidance_artifacts(mcp: FastMCP) -> None:
    @mcp.resource(OVERVIEW_URI)
    def google_mcp_guide_overview() -> str:
        """Overview of the Google MCP domains, capabilities, and decision rules."""
        return overview_guide()

    @mcp.resource(SAFETY_URI)
    def google_mcp_guide_safety() -> str:
        """Safety guidance for mutations across Calendar, Tasks, Gmail, and Drive."""
        return safety_guide()

    @mcp.resource(ERRORS_URI)
    def google_mcp_guide_error_handling() -> str:
        """How to interpret and recover from structured MCP errors."""
        return error_handling_guide()

    @mcp.resource(CALENDAR_URI)
    def google_mcp_guide_calendar() -> str:
        """Decision guide for Google Calendar tools, including recurring events."""
        return calendar_guide()

    @mcp.resource(TASKS_URI)
    def google_mcp_guide_tasks() -> str:
        """Decision guide for Google Tasks tools and task lifecycle actions."""
        return tasks_guide()

    @mcp.resource(GMAIL_URI)
    def google_mcp_guide_gmail() -> str:
        """Decision guide for Gmail message, thread, draft, and send actions."""
        return gmail_guide()

    @mcp.resource(DRIVE_URI)
    def google_mcp_guide_drive() -> str:
        """Decision guide for Drive read, export, prepare, confirm, and permission tools."""
        return drive_guide()

    @mcp.resource(CALENDAR_EXAMPLES_URI)
    def google_mcp_examples_calendar() -> str:
        """Canonical payload examples for Calendar operations."""
        return calendar_examples()

    @mcp.resource(CALENDAR_CONFIRM_EXAMPLES_URI)
    def google_mcp_examples_calendar_confirm() -> str:
        """Canonical payload examples for Calendar confirmation flows."""
        return calendar_confirm_examples()

    @mcp.resource(TASKS_EXAMPLES_URI)
    def google_mcp_examples_tasks() -> str:
        """Canonical payload examples for Tasks operations."""
        return tasks_examples()

    @mcp.resource(TASKS_CONFIRM_EXAMPLES_URI)
    def google_mcp_examples_tasks_confirm() -> str:
        """Canonical payload examples for Tasks confirmation flows."""
        return tasks_confirm_examples()

    @mcp.resource(GMAIL_EXAMPLES_URI)
    def google_mcp_examples_gmail() -> str:
        """Canonical payload examples for Gmail operations."""
        return gmail_examples()

    @mcp.resource(GMAIL_CONFIRM_EXAMPLES_URI)
    def google_mcp_examples_gmail_confirm() -> str:
        """Canonical payload examples for Gmail confirmation flows."""
        return gmail_confirm_examples()

    @mcp.resource(DRIVE_EXAMPLES_URI)
    def google_mcp_examples_drive() -> str:
        """Canonical payload examples for Drive operations."""
        return drive_examples()

    @mcp.resource(DRIVE_CONFIRM_EXAMPLES_URI)
    def google_mcp_examples_drive_confirm() -> str:
        """Canonical payload examples for Drive confirmation flows."""
        return drive_confirm_examples()

    @mcp.prompt
    def google_calendar_usage_prompt() -> str:
        """Prompt that summarizes how Calendar tools should be used."""
        return calendar_prompt_text()

    @mcp.prompt
    def google_tasks_usage_prompt() -> str:
        """Prompt that summarizes how Tasks tools should be used."""
        return tasks_prompt_text()

    @mcp.prompt
    def google_gmail_usage_prompt() -> str:
        """Prompt that summarizes how Gmail tools should be used."""
        return gmail_prompt_text()

    @mcp.prompt
    def google_drive_usage_prompt() -> str:
        """Prompt that summarizes how Drive tools should be used."""
        return drive_prompt_text()
