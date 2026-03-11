from fastmcp import FastMCP

from app.config import get_settings
from app.tools.auth_tools import register_auth_tools
from app.tools.calendar_tools import register_calendar_tools
from app.tools.common import register_ping_tool
from app.tools.gmail_tools import register_gmail_tools
from app.tools.tasks_tools import register_tasks_tools


settings = get_settings()
mcp = FastMCP(name=settings.mcp_server_name)

register_ping_tool(mcp, server_name=settings.mcp_server_name, server_version=settings.mcp_server_version)
register_auth_tools(mcp, settings=settings)
register_calendar_tools(mcp)
register_tasks_tools(mcp)
register_gmail_tools(mcp)
