from __future__ import annotations

import json
import logging
import random
import time
from typing import Any

from googleapiclient.errors import HttpError

from app.errors import (
    AppError,
    AuthenticationProviderError,
    ConflictProviderError,
    NotFoundProviderError,
    PermissionProviderError,
    PreconditionProviderError,
    ProviderError,
    RateLimitedError,
    TemporaryProviderError,
)

logger = logging.getLogger(__name__)


_RATE_LIMIT_REASONS = {
    "dailylimitexceeded",
    "quotaexceeded",
    "ratelimitexceeded",
    "userratelimitexceeded",
}

_AUTH_REASONS = {
    "autherror",
}

_PERMISSION_REASONS = {
    "forbidden",
    "forbiddenfornonorganizer",
    "insufficientpermissions",
}

_NOT_FOUND_REASONS = {
    "notfound",
}

_CONFLICT_REASONS = {
    "conflict",
    "duplicate",
}

_PRECONDITION_REASONS = {
    "conditionnotmet",
}

_TEMPORARY_REASONS = {
    "backenderror",
}


def map_google_http_error(exc: HttpError) -> AppError:
    error_payload = _extract_google_error_payload(exc)
    status_code = _coerce_int(getattr(exc.resp, "status", None))
    detail = _build_detail(exc=exc, error_payload=error_payload)
    metadata = _build_metadata(exc=exc, status_code=status_code, error_payload=error_payload)

    reason = _normalized_reason(metadata.get("provider_reason"))
    if reason in _RATE_LIMIT_REASONS:
        return RateLimitedError(
            detail,
            retry_after_seconds=metadata.get("retry_after_seconds"),
            metadata=metadata,
        )
    if reason in _AUTH_REASONS or status_code == 401:
        return AuthenticationProviderError(detail, metadata=metadata)
    if reason in _NOT_FOUND_REASONS or status_code == 404:
        return NotFoundProviderError(detail, metadata=metadata)
    if reason in _CONFLICT_REASONS or status_code == 409:
        return ConflictProviderError(detail, metadata=metadata)
    if reason in _PRECONDITION_REASONS or status_code == 412:
        return PreconditionProviderError(detail, metadata=metadata)
    if reason in _TEMPORARY_REASONS or (status_code is not None and 500 <= status_code <= 599):
        return TemporaryProviderError(detail, metadata=metadata)
    if reason in _PERMISSION_REASONS or status_code == 403:
        return PermissionProviderError(detail, metadata=metadata)
    if status_code == 429:
        return RateLimitedError(
            detail,
            retry_after_seconds=metadata.get("retry_after_seconds"),
            metadata=metadata,
        )
    return ProviderError(detail, metadata=metadata)


def execute_google_request(
    request: Any,
    *,
    max_retries: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    sleep_func: Any = time.sleep,
) -> Any:
    attempts = 0
    while True:
        try:
            return request.execute()
        except HttpError as exc:
            mapped_error = map_google_http_error(exc)
            if not mapped_error.retryable or attempts >= max_retries:
                raise mapped_error from None
            delay_seconds = _compute_retry_delay_seconds(
                attempts=attempts,
                mapped_error=mapped_error,
                base_delay_seconds=base_delay_seconds,
                max_delay_seconds=max_delay_seconds,
            )
            if delay_seconds > max_delay_seconds:
                raise mapped_error from None
            attempts += 1
            logger.warning(
                "Retrying Google API request after retryable error",
                extra={
                    "provider": "google",
                    "error_code": mapped_error.code,
                    "attempt": attempts,
                    "max_retries": max_retries,
                    "delay_seconds": delay_seconds,
                    "provider_status_code": mapped_error.metadata.get("provider_status_code")
                    if mapped_error.metadata
                    else None,
                    "provider_reason": mapped_error.metadata.get("provider_reason")
                    if mapped_error.metadata
                    else None,
                },
            )
            sleep_func(delay_seconds)


def execute_google_media_request(
    operation: Any,
    *,
    max_retries: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    sleep_func: Any = time.sleep,
) -> Any:
    attempts = 0
    while True:
        try:
            return operation()
        except HttpError as exc:
            mapped_error = map_google_http_error(exc)
            if not mapped_error.retryable or attempts >= max_retries:
                raise mapped_error from None
            delay_seconds = _compute_retry_delay_seconds(
                attempts=attempts,
                mapped_error=mapped_error,
                base_delay_seconds=base_delay_seconds,
                max_delay_seconds=max_delay_seconds,
            )
            if delay_seconds > max_delay_seconds:
                raise mapped_error from None
            attempts += 1
            logger.warning(
                "Retrying Google API media operation after retryable error",
                extra={
                    "provider": "google",
                    "error_code": mapped_error.code,
                    "attempt": attempts,
                    "max_retries": max_retries,
                    "delay_seconds": delay_seconds,
                    "provider_status_code": mapped_error.metadata.get("provider_status_code")
                    if mapped_error.metadata
                    else None,
                    "provider_reason": mapped_error.metadata.get("provider_reason")
                    if mapped_error.metadata
                    else None,
                },
            )
            sleep_func(delay_seconds)


def _extract_google_error_payload(exc: HttpError) -> dict[str, Any]:
    content = getattr(exc, "content", None)
    if content is None:
        return {}
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            return {}
    if not isinstance(content, str):
        return {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_detail(*, exc: HttpError, error_payload: dict[str, Any]) -> str:
    return "Google API request failed"


def _build_metadata(
    *, exc: HttpError, status_code: int | None, error_payload: dict[str, Any]
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "provider": "google",
        "provider_status_code": status_code,
    }

    error = error_payload.get("error")
    if isinstance(error, dict):
        code = _coerce_int(error.get("code"))
        if code is not None:
            metadata["provider_error_code"] = code

        errors = error.get("errors")
        if isinstance(errors, list):
            first_error = next((item for item in errors if isinstance(item, dict)), None)
            if first_error:
                reason = first_error.get("reason")
                if isinstance(reason, str) and reason:
                    metadata["provider_reason"] = (
                        reason
                        if reason.lower()
                        in (
                            _RATE_LIMIT_REASONS
                            | _AUTH_REASONS
                            | _PERMISSION_REASONS
                            | _NOT_FOUND_REASONS
                            | _CONFLICT_REASONS
                            | _PRECONDITION_REASONS
                            | _TEMPORARY_REASONS
                        )
                        else "other"
                    )
                domain = first_error.get("domain")
                if isinstance(domain, str) and domain:
                    metadata["provider_domain"] = (
                        domain if domain in {"global", "usageLimits"} else "other"
                    )

    retry_after_seconds = _extract_retry_after_seconds(exc)
    if retry_after_seconds is not None:
        metadata["retry_after_seconds"] = retry_after_seconds
    return metadata


def _extract_retry_after_seconds(exc: HttpError) -> int | None:
    resp = getattr(exc, "resp", None)
    if resp is None:
        return None
    retry_after = None
    if hasattr(resp, "get"):
        retry_after = resp.get("retry-after") or resp.get("Retry-After")
    return _coerce_int(retry_after)


def _normalized_reason(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _compute_retry_delay_seconds(
    *,
    attempts: int,
    mapped_error: AppError,
    base_delay_seconds: float,
    max_delay_seconds: float,
) -> float:
    retry_after_seconds = None
    if mapped_error.metadata:
        retry_after_seconds = _coerce_int(mapped_error.metadata.get("retry_after_seconds"))
    if retry_after_seconds is not None and retry_after_seconds > 0:
        return float(retry_after_seconds)

    bounded_base = max(base_delay_seconds, 0.0)
    bounded_cap = max(max_delay_seconds, bounded_base if bounded_base > 0 else 0.0)
    if bounded_base == 0:
        return 0.0

    exponential_delay = bounded_base * (2**attempts)
    capped_delay = min(exponential_delay, bounded_cap)
    jitter_floor = capped_delay / 2 if capped_delay > 0 else 0.0
    return random.uniform(jitter_floor, capped_delay)
