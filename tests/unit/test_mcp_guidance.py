from __future__ import annotations

import inspect

from app import mcp_guidance
from app.tools import drive_tools


def test_overview_guide_mentions_all_supported_domains() -> None:
    content = mcp_guidance.overview_guide()

    assert "Calendar" in content
    assert "Tasks" in content
    assert "Gmail" in content
    assert "Drive" in content


def test_calendar_guide_mentions_recurrence_rule() -> None:
    content = mcp_guidance.calendar_guide()

    assert "event.recurrence" in content
    assert "Do not create multiple events" in content


def test_drive_guide_mentions_prepare_and_confirm_pattern() -> None:
    content = mcp_guidance.drive_guide()

    assert "prepare_* tools" in content
    assert "confirm_* tools" in content


def test_example_resources_include_canonical_payloads() -> None:
    assert "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR" in mcp_guidance.calendar_examples()
    assert "tasklist_id" in mcp_guidance.tasks_examples()
    assert "body_text" in mcp_guidance.gmail_examples()
    assert "export_mime_type" in mcp_guidance.drive_examples()
    assert "Sistema de Notas de Proyectos" in mcp_guidance.drive_examples()
    assert '"file_type": "doc"' in mcp_guidance.drive_examples()


def test_confirm_example_resources_include_operation_ids() -> None:
    assert "calendar_delete_event" in mcp_guidance.calendar_confirm_examples()
    assert "tasks_delete_task" in mcp_guidance.tasks_confirm_examples()
    assert "gmail_send_email" in mcp_guidance.gmail_confirm_examples()
    assert "drive_prepare_upload" in mcp_guidance.drive_confirm_examples()


def test_key_tool_docstrings_include_drive_smart_find_examples() -> None:
    assert "Example payload:" in inspect.getsource(drive_tools)
    assert "drive_find_folder_by_name" in inspect.getsource(drive_tools)
    assert "drive_find_file_by_name" in inspect.getsource(drive_tools)
    assert "drive_search_files_advanced" in inspect.getsource(drive_tools)
    assert '"name": "Sistema de Notas de Proyectos"' in inspect.getsource(drive_tools)
    assert '"file_type": "doc"' in inspect.getsource(drive_tools)
