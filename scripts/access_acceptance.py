"""Explicit Google Tasks write acceptance in a new, dedicated list; never prints credentials."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


async def run(url: str, token: str) -> dict[str, object]:
    transport = StreamableHttpTransport(url=url, headers={"Authorization": "Bearer " + token})
    async with Client(transport) as client:

        async def call(name, arguments):
            result = await client.call_tool(name, arguments)
            return json.loads(result.content[0].text)

        access = await call("auth_get_permissions", {})
        if (
            access["authorization_mode"] != "server_policy"
            or access["access_profile"] != "read_write"
        ):
            raise RuntimeError("Acceptance requires server_policy and read_write access")
        title = (
            "MCP acceptance " + datetime.now(UTC).strftime("%Y-%m-%d %H:%M") + " " + uuid4().hex[:8]
        )
        tasklist = await call("tasks_create_tasklist", {"title": title})
        list_id = tasklist["id"]
        print(json.dumps({"test_list_id": list_id, "title": title}), flush=True)
        task = await call(
            "tasks_create_task", {"tasklist_id": list_id, "task": {"title": "MCP test"}}
        )
        task_id = task["id"]
        edited = await call(
            "tasks_update_task",
            {
                "tasklist_id": list_id,
                "task_id": task_id,
                "task": {"title": "MCP test edited"},
            },
        )
        assert edited["title"] == "MCP test edited"
        preview = await call("tasks_delete_task", {"tasklist_id": list_id, "task_id": task_id})
        assert preview["summary"]["task_id"] == task_id
        assert preview["summary"]["tasklist_id"] == list_id
        deleted = await call(preview["confirmation_tool"], preview["confirmation_arguments"])
        assert deleted["deleted"] is True
        remaining = await call("tasks_list_tasks", {"tasklist_id": list_id})
        assert not remaining["items"]
        preview = await call("tasks_delete_tasklist", {"tasklist_id": list_id})
        assert preview["summary"]["tasklist_id"] == list_id
        assert preview["summary"]["title"] == title
        deleted_list = await call(preview["confirmation_tool"], preview["confirmation_arguments"])
        assert deleted_list["deleted"] is True
        return {
            "same_jwt": True,
            "created": True,
            "edited": True,
            "deleted": True,
            "test_list_removed": True,
            "authorization_mode": access["authorization_mode"],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token-file", required=True, type=Path)
    args = parser.parse_args()
    # On failure do not blindly clean up: a provider timeout can mean the write happened.
    print(json.dumps(asyncio.run(run(args.url, args.token_file.read_text().strip()))))


if __name__ == "__main__":
    main()
