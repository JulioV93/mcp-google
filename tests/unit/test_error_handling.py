from __future__ import annotations

from unittest.mock import Mock

from googleapiclient.errors import HttpError
from httplib2 import Response

from app.errors import InternalError, PermissionProviderError, ProviderError
from app.google.errors import map_google_http_error
from app.tool_runtime import audited_call


def make_http_error(status: int, content: bytes = b'{"error":"boom"}') -> HttpError:
    return HttpError(Response({"status": str(status)}), content)


def test_google_403_maps_to_permission_provider_error() -> None:
    error = map_google_http_error(make_http_error(403))

    assert isinstance(error, PermissionProviderError)
    assert error.code == "insufficient_scope"
    assert error.status_code == 403
    assert error.retryable is False
    assert error.category == "provider"


def test_google_503_maps_to_temporary_provider_error() -> None:
    error = map_google_http_error(make_http_error(503))

    assert isinstance(error, ProviderError)
    assert error.code == "provider_temporary_error"
    assert error.status_code == 503
    assert error.retryable is True


def test_audited_call_preserves_app_error() -> None:
    try:
        audited_call(
            external_subject="user-1",
            tenant_id=None,
            tool_name="gmail_list_messages",
            provider="google",
            resource_type="gmail_message",
            arguments={},
            operation=lambda session: (_ for _ in ()).throw(PermissionProviderError("missing scope")),
        )
    except PermissionProviderError as exc:
        assert exc.code == "insufficient_scope"
    else:
        raise AssertionError("Expected PermissionProviderError to be preserved")


def test_audited_call_converts_unexpected_exception_to_internal_error() -> None:
    try:
        audited_call(
            external_subject="user-1",
            tenant_id=None,
            tool_name="gmail_list_messages",
            provider="google",
            resource_type="gmail_message",
            arguments={},
            operation=lambda session: (_ for _ in ()).throw(ValueError("boom")),
        )
    except InternalError as exc:
        assert exc.code == "internal_error"
        assert exc.status_code == 500
        assert exc.category == "internal"
        assert exc.metadata == {"tool_name": "gmail_list_messages"}
    else:
        raise AssertionError("Expected InternalError for unexpected exception")
