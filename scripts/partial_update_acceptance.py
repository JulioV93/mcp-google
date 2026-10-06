"""Accept partial updates on dedicated Google test resources; stop on uncertain outcomes."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
from pathlib import Path
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


async def run(url: str, token: str, report_file: Path) -> dict[str, object]:
    report: dict[str, object] = {"checks": {}, "resources": {}}
    checks, resources = report["checks"], report["resources"]

    def checkpoint(stage):
        report["stage"] = stage
        descriptor = os.open(report_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(report, stream, indent=2)

    transport = StreamableHttpTransport(url=url, headers={"Authorization": "Bearer " + token})
    async with Client(transport) as client:

        async def call(name, arguments):
            checkpoint(name)
            response = await client.call_tool(name, arguments)
            return json.loads(response.content[0].text)

        permissions = await call("auth_get_permissions", {})
        if permissions.get("access_profile") != "read_write":
            raise RuntimeError("Acceptance requires read_write access")
        marker = "MCP partial acceptance " + uuid4().hex
        tasklist = await call("tasks_create_tasklist", {"title": marker})
        resources["tasklist_id"] = tasklist["id"]
        task = await call(
            "tasks_create_task",
            {
                "tasklist_id": tasklist["id"],
                "task": {"title": marker},
            },
        )
        resources["task_id"] = task["id"]
        task_ref = {"tasklist_id": tasklist["id"], "task_id": task["id"]}
        edited = await call(
            "tasks_update_task",
            {
                **task_ref,
                "task": {"due": "2026-11-14T00:00:00Z", "notes": marker},
            },
        )
        assert edited["title"] == marker and edited["due"].startswith("2026-11-14")
        assert edited["notes"] == marker
        checks["task_partial_update"] = True
        cleared = await call("tasks_update_task", {**task_ref, "task": {"due": None}})
        assert cleared.get("due") is None and cleared["title"] == marker
        listed = await call("tasks_list_tasks", {"tasklist_id": tasklist["id"]})
        persisted = next(item for item in listed["items"] if item["id"] == task["id"])
        assert persisted.get("due") is None and persisted["notes"] == marker
        checks["task_due_cleared_and_read_back"] = True

        event = await call(
            "calendar_create_event",
            {
                "calendar_id": "primary",
                "event": {
                    "summary": marker,
                    "start": {"dateTime": "2030-01-01T10:00:00Z"},
                    "end": {"dateTime": "2030-01-01T10:30:00Z"},
                },
            },
        )
        resources["event_id"] = event["id"]
        event_ref = {"calendar_id": "primary", "event_id": event["id"]}
        await call("calendar_update_event", {**event_ref, "event": {"description": marker}})
        read_event = await call("calendar_get_event", event_ref)
        assert read_event["description"] == marker and read_event["summary"] == marker
        assert read_event["start"] == event["start"] and read_event["end"] == event["end"]
        checks["calendar_description_only_preserves_schedule"] = True

        doc = await call("drive_create_google_doc", {"name": marker})
        resources["file_id"] = doc["id"]
        prepared = await call(
            "drive_prepare_write_google_doc",
            {
                "file_id": doc["id"],
                "content_text": marker,
                "mode": "append",
            },
        )
        await call(prepared["confirmation_tool"], prepared["confirmation_arguments"])
        exported = await call(
            "drive_export_file",
            {
                "file_id": doc["id"],
                "export_mime_type": "text/plain",
            },
        )
        assert base64.b64decode(exported["content_base64"]).decode("utf-8").count(marker) == 1
        checks["doc_append_exactly_once"] = True

        # Only delete resources created above, and only after every acceptance check passed.
        for tool, arguments in [
            ("tasks_delete_tasklist", {"tasklist_id": tasklist["id"]}),
            ("calendar_delete_event", event_ref),
            ("drive_prepare_delete_file", {"file_id": doc["id"]}),
        ]:
            preview = await call(tool, arguments)
            await call(preview["confirmation_tool"], preview["confirmation_arguments"])
        checks["test_resources_removed"] = True
        checkpoint("complete")
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--report-file", required=True, type=Path)
    arguments = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(
                run(
                    arguments.url,
                    arguments.token_file.read_text().strip(),
                    arguments.report_file,
                )
            )
        )
    )


if __name__ == "__main__":
    main()
