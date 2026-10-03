from fastmcp import FastMCP

from app.config import get_settings
from app.mcp_guidance import register_guidance_artifacts
from app.tools.auth_tools import register_auth_tools
from app.tools.calendar_tools import register_calendar_tools
from app.tools.common import register_ping_tool
from app.tools.drive_tools import register_drive_tools
from app.tools.gmail_tools import register_gmail_tools
from app.tools.tasks_tools import register_tasks_tools

settings = get_settings()
mcp = FastMCP(
    name=settings.mcp_server_name,
    instructions=(
        "Use auth_get_permissions to inspect access. In server_policy mode, writes use the same JWT. "
        "An explicit, unambiguous user request authorizes its complete workflow: create/edit directly; "
        "for prepared operations review the preview and call confirmation_tool with "
        "confirmation_arguments. requires_confirmation means a technical tool call, not necessarily "
        "another user approval. Clarify ambiguity or a changed scope before executing. "
        "Respect the client's approval policy. Never retry uncertain writes."
    ),
)

register_ping_tool(
    mcp, server_name=settings.mcp_server_name, server_version=settings.mcp_server_version
)
register_guidance_artifacts(mcp)
register_auth_tools(mcp, settings=settings)
register_calendar_tools(mcp)
register_tasks_tools(mcp)
register_gmail_tools(mcp)
register_drive_tools(mcp)
