from __future__ import annotations

import json
from unittest.mock import Mock

from googleapiclient.errors import HttpError
from httplib2 import Response

from app.errors import InternalError, PermissionProviderError, ProviderError, RateLimitedError
from app.google.errors import (
    execute_google_media_request,
    execute_google_request,
    map_google_http_error,
)
from app.tool_runtime import audited_call


def make_http_error(
    status: int,
    content: bytes | None = None,
    *,
    headers: dict[str, str] | None = None,
) -> HttpError:
    response_headers = {"status": str(status)}
    if headers:
        response_headers.update(headers)
    if content is None:
        content = json.dumps({"error": {"code": status, "message": "boom"}}).encode("utf-8")
    return HttpError(Response(response_headers), content)


def make_google_error_payload(
    *, status: int, reason: str, message: str, domain: str = "global"
) -> bytes:
    return json.dumps(
        {
            "error": {
                "errors": [
                    {
                        "domain": domain,
                        "reason": reason,
                        "message": message,
                    }
                ],
                "code": status,
                "message": message,
            }
        }
    ).encode("utf-8")


def test_google_403_maps_to_permission_provider_error() -> None:
    error = map_google_http_error(
        make_http_error(
            403,
            make_google_error_payload(
                status=403,
                reason="insufficientPermissions",
                message="Request had insufficient authentication scopes.",
            ),
        )
    )

    assert isinstance(error, PermissionProviderError)
    assert error.code == "insufficient_scope"
    assert error.status_code == 403
    assert error.retryable is False
    assert error.category == "provider"
    assert error.metadata == {
        "provider": "google",
        "provider_status_code": 403,
        "provider_error_code": 403,
        "provider_reason": "insufficientPermissions",
        "provider_domain": "global",
    }


def test_google_403_rate_limit_maps_to_rate_limited_error() -> None:
    error = map_google_http_error(
        make_http_error(
            403,
            make_google_error_payload(
                status=403,
                reason="rateLimitExceeded",
                message="Rate Limit Exceeded",
                domain="usageLimits",
            ),
            headers={"retry-after": "120"},
        )
    )

    assert isinstance(error, RateLimitedError)
    assert error.code == "rate_limited"
    assert error.status_code == 429
    assert error.retryable is True
    assert error.category == "rate_limit"
    assert error.metadata == {
        "provider": "google",
        "provider_status_code": 403,
        "provider_error_code": 403,
        "provider_reason": "rateLimitExceeded",
        "provider_domain": "usageLimits",
        "retry_after_seconds": 120,
    }


def test_google_403_quota_exceeded_maps_to_rate_limited_error() -> None:
    error = map_google_http_error(
        make_http_error(
            403,
            make_google_error_payload(
                status=403,
                reason="quotaExceeded",
                message="Calendar usage limits exceeded.",
                domain="usageLimits",
            ),
        )
    )

    assert isinstance(error, RateLimitedError)
    assert error.code == "rate_limited"
    assert error.retryable is True
    assert error.metadata == {
        "provider": "google",
        "provider_status_code": 403,
        "provider_error_code": 403,
        "provider_reason": "quotaExceeded",
        "provider_domain": "usageLimits",
    }


def test_google_429_maps_to_rate_limited_error() -> None:
    error = map_google_http_error(
        make_http_error(
            429,
            make_google_error_payload(
                status=429,
                reason="rateLimitExceeded",
                message="Rate Limit Exceeded",
                domain="usageLimits",
            ),
        )
    )

    assert isinstance(error, RateLimitedError)
    assert error.code == "rate_limited"
    assert error.status_code == 429
    assert error.retryable is True


def test_google_503_maps_to_temporary_provider_error() -> None:
    error = map_google_http_error(
        make_http_error(
            503,
            make_google_error_payload(
                status=503,
                reason="backendError",
                message="Backend Error",
            ),
        )
    )

    assert isinstance(error, ProviderError)
    assert error.code == "provider_temporary_error"
    assert error.status_code == 503
    assert error.retryable is True
    assert error.metadata == {
        "provider": "google",
        "provider_status_code": 503,
        "provider_error_code": 503,
        "provider_reason": "backendError",
        "provider_domain": "global",
    }


def test_google_409_duplicate_maps_to_conflict_error() -> None:
    error = map_google_http_error(
        make_http_error(
            409,
            make_google_error_payload(
                status=409,
                reason="duplicate",
                message="The requested identifier already exists.",
            ),
        )
    )

    assert isinstance(error, ProviderError)
    assert error.code == "provider_conflict"
    assert error.status_code == 409
    assert error.retryable is False
    assert error.metadata == {
        "provider": "google",
        "provider_status_code": 409,
        "provider_error_code": 409,
        "provider_reason": "duplicate",
        "provider_domain": "global",
    }


def test_google_412_condition_not_met_maps_to_precondition_error() -> None:
    error = map_google_http_error(
        make_http_error(
            412,
            make_google_error_payload(
                status=412,
                reason="conditionNotMet",
                message="Precondition Failed",
            ),
        )
    )

    assert isinstance(error, ProviderError)
    assert error.code == "provider_precondition_failed"
    assert error.status_code == 412
    assert error.retryable is False
    assert error.metadata == {
        "provider": "google",
        "provider_status_code": 412,
        "provider_error_code": 412,
        "provider_reason": "conditionNotMet",
        "provider_domain": "global",
    }


def test_google_403_forbidden_for_non_organizer_maps_to_permission_error() -> None:
    error = map_google_http_error(
        make_http_error(
            403,
            make_google_error_payload(
                status=403,
                reason="forbiddenForNonOrganizer",
                message="Shared properties can only be changed by the organizer of the event.",
            ),
        )
    )

    assert isinstance(error, PermissionProviderError)
    assert error.code == "insufficient_scope"
    assert error.status_code == 403
    assert error.retryable is False


def test_execute_google_request_retries_then_succeeds() -> None:
    request = Mock()
    request.execute.side_effect = [
        make_http_error(
            429,
            make_google_error_payload(
                status=429,
                reason="rateLimitExceeded",
                message="Rate Limit Exceeded",
                domain="usageLimits",
            ),
            headers={"retry-after": "1"},
        ),
        {"ok": True},
    ]
    sleep = Mock()

    result = execute_google_request(
        request,
        max_retries=2,
        base_delay_seconds=0.5,
        max_delay_seconds=2.0,
        sleep_func=sleep,
    )

    assert result == {"ok": True}
    assert request.execute.call_count == 2
    sleep.assert_called_once_with(1.0)


def test_execute_google_request_raises_after_retry_budget_exhausted() -> None:
    request = Mock()
    request.execute.side_effect = [
        make_http_error(
            500,
            make_google_error_payload(
                status=500,
                reason="backendError",
                message="Backend Error",
            ),
        ),
        make_http_error(
            500,
            make_google_error_payload(
                status=500,
                reason="backendError",
                message="Backend Error",
            ),
        ),
    ]
    sleep = Mock()

    try:
        execute_google_request(
            request,
            max_retries=1,
            base_delay_seconds=0,
            max_delay_seconds=0,
            sleep_func=sleep,
        )
    except ProviderError as exc:
        assert exc.code == "provider_temporary_error"
        assert exc.retryable is True
    else:
        raise AssertionError("Expected retryable provider error after retries are exhausted")

    assert request.execute.call_count == 2
    sleep.assert_called_once_with(0.0)


def test_execute_google_media_request_retries_operation() -> None:
    operation = Mock(
        side_effect=[
            make_http_error(
                403,
                make_google_error_payload(
                    status=403,
                    reason="userRateLimitExceeded",
                    message="User Rate Limit Exceeded",
                    domain="usageLimits",
                ),
            ),
            b"payload",
        ]
    )
    sleep = Mock()

    result = execute_google_media_request(
        operation,
        max_retries=2,
        base_delay_seconds=0,
        max_delay_seconds=0,
        sleep_func=sleep,
    )

    assert result == b"payload"
    assert operation.call_count == 2
    sleep.assert_called_once_with(0.0)


def test_audited_call_preserves_app_error() -> None:
    try:
        audited_call(
            external_subject="user-1",
            tenant_id=None,
            tool_name="gmail_list_messages",
            provider="google",
            resource_type="gmail_message",
            arguments={},
            operation=lambda session: (_ for _ in ()).throw(
                PermissionProviderError("missing scope")
            ),
        )
    except PermissionProviderError as exc:
        assert exc.code == "insufficient_scope"
    else:
        raise AssertionError("Expected PermissionProviderError to be preserved")


def test_audited_call_preserves_rate_limited_error() -> None:
    try:
        audited_call(
            external_subject="user-1",
            tenant_id=None,
            tool_name="calendar_update_event",
            provider="google",
            resource_type="calendar_event",
            arguments={},
            operation=lambda session: (_ for _ in ()).throw(
                RateLimitedError("Rate Limit Exceeded")
            ),
        )
    except RateLimitedError as exc:
        assert exc.code == "rate_limited"
        assert exc.retryable is True
    else:
        raise AssertionError("Expected RateLimitedError to be preserved")


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
