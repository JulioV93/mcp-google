from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest

from scripts import partial_update_acceptance


@pytest.mark.parametrize("uncertain", [False, True])
async def test_acceptance_verifies_export_and_stops_without_cleanup_on_uncertain_write(
    monkeypatch, tmp_path, uncertain
):
    calls = []
    state = {}

    class FakeClient:
        def __init__(self, transport):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def call_tool(self, name, arguments):
            calls.append(name)
            if name == "auth_get_permissions":
                result = {"access_profile": "read_write"}
            elif name == "tasks_create_tasklist":
                result = {"id": "list"}
            elif name == "tasks_create_task":
                state["task"] = {"id": "task", **arguments["task"]}
                result = state["task"]
            elif name == "tasks_update_task":
                state["task"].update(arguments["task"])
                result = state["task"]
            elif name == "tasks_list_tasks":
                result = {"items": [state["task"]]}
            elif name == "calendar_create_event":
                state["event"] = {"id": "event", **arguments["event"]}
                result = state["event"]
            elif name == "calendar_update_event":
                state["event"].update(arguments["event"])
                result = state["event"]
            elif name == "calendar_get_event":
                result = state["event"]
            elif name == "drive_create_google_doc":
                result = {"id": "doc"}
            elif name == "drive_prepare_write_google_doc":
                state["content"] = arguments["content_text"]
                result = {
                    "confirmation_tool": "drive_confirm_write_google_doc",
                    "confirmation_arguments": {"operation_id": "operation"},
                }
            elif name == "drive_confirm_write_google_doc":
                if uncertain:
                    raise RuntimeError("Uncertain external result")
                result = {"confirmed": True}
            elif name == "drive_export_file":
                result = {"content_base64": base64.b64encode(state["content"].encode()).decode()}
            elif name in {
                "tasks_delete_tasklist",
                "calendar_delete_event",
                "drive_prepare_delete_file",
            }:
                result = {
                    "confirmation_tool": "test_confirm_delete",
                    "confirmation_arguments": {"operation_id": "delete"},
                }
            else:
                assert name == "test_confirm_delete"
                result = {"deleted": True}
            return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(result))])

    monkeypatch.setattr(partial_update_acceptance, "Client", FakeClient)
    report_file = tmp_path / "report.json"
    if uncertain:
        with pytest.raises(RuntimeError, match="Uncertain"):
            await partial_update_acceptance.run(
                "https://example.com/mcp", "test-token", report_file
            )
        assert not any("delete" in name for name in calls)
        assert calls.count("drive_confirm_write_google_doc") == 1
    else:
        checks = await partial_update_acceptance.run(
            "https://example.com/mcp", "test-token", report_file
        )
        assert all(checks.values()) and checks["test_resources_removed"]
    assert report_file.stat().st_mode & 0o777 == 0o600
    report = json.loads(report_file.read_text())
    assert report["resources"] == {
        "tasklist_id": "list",
        "task_id": "task",
        "event_id": "event",
        "file_id": "doc",
    }
    assert "test-token" not in report_file.read_text()
