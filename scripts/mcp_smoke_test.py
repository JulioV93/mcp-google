from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a basic authenticated MCP smoke test")
    parser.add_argument("--url", default="http://localhost:8000/mcp", help="MCP server URL")
    parser.add_argument(
        "--token",
        default="local-dev-token",
        help="Bearer token used to authenticate against the MCP server",
    )
    parser.add_argument(
        "--tool",
        default=None,
        help="Optional tool name to call after listing tools",
    )
    parser.add_argument(
        "--args",
        default="{}",
        help="JSON object with tool arguments when --tool is provided",
    )
    return parser


async def run_smoke_test(url: str, token: str, tool_name: str | None, tool_args: dict[str, Any]) -> None:
    transport = StreamableHttpTransport(
        url=url,
        headers={"Authorization": f"Bearer {token}"},
    )

    async with Client(transport) as client:
        tools = await client.list_tools()
        print("Available tools:")
        for tool in tools:
            print(f"- {tool.name}")

        if tool_name:
            print(f"\nCalling tool: {tool_name}")
            result = await client.call_tool(tool_name, tool_args)
            print(result)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    tool_args = json.loads(args.args)
    if not isinstance(tool_args, dict):
        raise SystemExit("--args must decode to a JSON object")
    asyncio.run(run_smoke_test(args.url, args.token, args.tool, tool_args))


if __name__ == "__main__":
    main()
