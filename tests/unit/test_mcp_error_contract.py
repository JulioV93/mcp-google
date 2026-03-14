from __future__ import annotations

import json

from fastmcp.exceptions import ToolError

from app.errors import PermissionProviderError


def test_app_error_serializes_to_tool_error_json() -> None:
    error = PermissionProviderError("Request had insufficient authentication scopes.")

    tool_error = error.to_tool_error()

    assert isinstance(tool_error, ToolError)
    payload = json.loads(str(tool_error))
    assert payload == {
        "error": "insufficient_scope",
        "detail": "Request had insufficient authentication scopes.",
        "retryable": False,
        "category": "provider",
    }
