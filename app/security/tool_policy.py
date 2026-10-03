"""Explicit operation catalog shared by authorization and MCP annotations."""

from dataclasses import dataclass
from typing import Literal

OperationKind = Literal["read", "prepare", "write", "connection"]


@dataclass(frozen=True)
class ToolPolicy:
    kind: OperationKind
    destructive: bool = False


READ_TOOLS = frozenset(
    {
        "ping",
        "auth_google_status",
        "auth_get_permissions",
        "calendar_list_calendars",
        "calendar_list_events",
        "calendar_get_event",
        "tasks_list_tasklists",
        "tasks_list_tasks",
        "gmail_list_messages",
        "gmail_get_message",
        "gmail_list_threads",
        "drive_list_files",
        "drive_search_files",
        "drive_get_file",
        "drive_find_folder_by_name",
        "drive_find_file_by_name",
        "drive_search_files_advanced",
        "drive_list_permissions",
        "drive_download_file",
        "drive_export_file",
    }
)
PREPARE_TOOLS = frozenset(
    {
        "calendar_delete_event",
        "tasks_delete_task",
        "tasks_delete_tasklist",
        "gmail_send_email",
        "drive_prepare_upload",
        "drive_prepare_save_file",
        "drive_prepare_write_google_doc",
        "drive_prepare_write_google_sheet",
        "drive_prepare_upload_markdown",
        "drive_prepare_delete_file",
        "drive_prepare_share_file",
        "drive_prepare_revoke_permission",
    }
)
WRITE_TOOLS = frozenset(
    {
        "auth_google_disconnect",
        "calendar_create_event",
        "calendar_update_event",
        "calendar_confirm_delete_event",
        "tasks_create_tasklist",
        "tasks_update_tasklist",
        "tasks_create_task",
        "tasks_update_task",
        "tasks_complete_task",
        "tasks_confirm_delete_task",
        "tasks_confirm_delete_tasklist",
        "gmail_create_draft",
        "gmail_update_draft",
        "gmail_delete_draft",
        "gmail_confirm_send_email",
        "gmail_delete_message",
        "drive_create_folder",
        "drive_create_google_doc",
        "drive_create_google_sheet",
        "drive_create_google_slide",
        "drive_create_shortcut",
        "drive_update_metadata",
        "drive_move_file",
        "drive_confirm_write_google_doc",
        "drive_confirm_write_google_sheet",
        "drive_confirm_upload",
        "drive_confirm_save_file",
        "drive_confirm_delete_file",
        "drive_confirm_share_file",
        "drive_confirm_revoke_permission",
    }
)
DESTRUCTIVE_TOOLS = frozenset(
    {
        "auth_google_disconnect",
        "calendar_update_event",
        "calendar_confirm_delete_event",
        "tasks_update_tasklist",
        "tasks_update_task",
        "tasks_complete_task",
        "tasks_confirm_delete_task",
        "tasks_confirm_delete_tasklist",
        "gmail_update_draft",
        "gmail_delete_draft",
        "gmail_delete_message",
        "drive_update_metadata",
        "drive_move_file",
        "drive_confirm_write_google_doc",
        "drive_confirm_write_google_sheet",
        "drive_confirm_save_file",
        "drive_confirm_delete_file",
        "drive_confirm_revoke_permission",
    }
)
TOOL_POLICIES = {
    **{name: ToolPolicy("read") for name in READ_TOOLS},
    **{name: ToolPolicy("prepare") for name in PREPARE_TOOLS},
    **{name: ToolPolicy("write", name in DESTRUCTIVE_TOOLS) for name in WRITE_TOOLS},
    "auth_google_begin": ToolPolicy("connection"),
}


def tool_annotations(name: str) -> dict[str, bool]:
    policy = TOOL_POLICIES[name]  # Unclassified tools cannot be registered.
    return {
        "readOnlyHint": policy.kind == "read",
        "destructiveHint": policy.destructive,
        "idempotentHint": policy.kind == "read",
        "openWorldHint": name not in {"ping", "auth_get_permissions"},
    }
