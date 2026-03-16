from __future__ import annotations

import json

from fastmcp.exceptions import ToolError

from app.errors import PermissionProviderError, PreconditionProviderError, RateLimitedError


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


def test_rate_limited_error_serializes_metadata_to_tool_error_json() -> None:
    error = RateLimitedError(
        "Rate Limit Exceeded",
        retry_after_seconds=120,
        metadata={
            "provider": "google",
            "provider_status_code": 403,
            "provider_reason": "rateLimitExceeded",
        },
    )

    tool_error = error.to_tool_error()

    assert isinstance(tool_error, ToolError)
    payload = json.loads(str(tool_error))
    assert payload == {
        "error": "rate_limited",
        "detail": "Rate Limit Exceeded",
        "retryable": True,
        "category": "rate_limit",
        "metadata": {
            "provider": "google",
            "provider_status_code": 403,
            "provider_reason": "rateLimitExceeded",
            "retry_after_seconds": 120,
        },
    }


def test_precondition_error_serializes_to_tool_error_json() -> None:
    error = PreconditionProviderError(
        "Precondition Failed",
        metadata={
            "provider": "google",
            "provider_status_code": 412,
            "provider_reason": "conditionNotMet",
        },
    )

    tool_error = error.to_tool_error()

    assert isinstance(tool_error, ToolError)
    payload = json.loads(str(tool_error))
    assert payload == {
        "error": "provider_precondition_failed",
        "detail": "Precondition Failed",
        "retryable": False,
        "category": "provider",
        "metadata": {
            "provider": "google",
            "provider_status_code": 412,
            "provider_reason": "conditionNotMet",
        },
    }
