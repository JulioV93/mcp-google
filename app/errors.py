from __future__ import annotations

import json
from typing import Any

from fastmcp.exceptions import ToolError


class AppError(Exception):
    def __init__(
        self,
        code: str,
        detail: str,
        *,
        status_code: int,
        retryable: bool,
        category: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code
        self.retryable = retryable
        self.category = category
        self.metadata = metadata

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "error": self.code,
            "detail": self.detail,
            "retryable": self.retryable,
            "category": self.category,
        }
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    def to_tool_error(self) -> ToolError:
        return ToolError(json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=True))


class UnauthorizedError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            "unauthorized_client",
            detail,
            status_code=401,
            retryable=False,
            category="auth",
        )


class RateLimitedError(AppError):
    def __init__(self, detail: str, *, retry_after_seconds: int | None = None) -> None:
        metadata = {"retry_after_seconds": retry_after_seconds} if retry_after_seconds is not None else None
        super().__init__(
            "rate_limited",
            detail,
            status_code=429,
            retryable=True,
            category="rate_limit",
            metadata=metadata,
        )


class ProviderError(AppError):
    def __init__(
        self,
        detail: str,
        *,
        code: str = "provider_error",
        status_code: int = 502,
        retryable: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            detail,
            status_code=status_code,
            retryable=retryable,
            category="provider",
            metadata=metadata,
        )


class AuthenticationProviderError(ProviderError):
    def __init__(self, detail: str, *, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(
            detail,
            code="google_consent_required",
            status_code=401,
            retryable=False,
            metadata=metadata,
        )


class NotFoundProviderError(ProviderError):
    def __init__(self, detail: str, *, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(
            detail,
            code="resource_not_found",
            status_code=404,
            retryable=False,
            metadata=metadata,
        )


class PermissionProviderError(ProviderError):
    def __init__(self, detail: str, *, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(
            detail,
            code="insufficient_scope",
            status_code=403,
            retryable=False,
            metadata=metadata,
        )


class TemporaryProviderError(ProviderError):
    def __init__(self, detail: str, *, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(
            detail,
            code="provider_temporary_error",
            status_code=503,
            retryable=True,
            metadata=metadata,
        )


class InternalError(AppError):
    def __init__(self, detail: str = "Internal server error", *, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(
            "internal_error",
            detail,
            status_code=500,
            retryable=False,
            category="internal",
            metadata=metadata,
        )


class ConfigurationError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            "configuration_error",
            detail,
            status_code=500,
            retryable=False,
            category="internal",
        )


class ValidationError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            "validation_error",
            detail,
            status_code=400,
            retryable=False,
            category="validation",
        )


class DriveOperationNotFoundError(AppError):
    def __init__(self, detail: str = "Drive confirmation operation was not found") -> None:
        super().__init__(
            "google_drive_operation_not_found",
            detail,
            status_code=404,
            retryable=False,
            category="validation",
        )


class DriveOperationExpiredError(AppError):
    def __init__(self, detail: str = "Drive confirmation operation has expired") -> None:
        super().__init__(
            "google_drive_operation_expired",
            detail,
            status_code=410,
            retryable=False,
            category="validation",
        )


class DriveOperationConsumedError(AppError):
    def __init__(self, detail: str = "Drive confirmation operation was already consumed") -> None:
        super().__init__(
            "google_drive_operation_already_consumed",
            detail,
            status_code=409,
            retryable=False,
            category="validation",
        )


class DrivePayloadMismatchError(AppError):
    def __init__(self, detail: str = "Drive confirmation payload integrity check failed") -> None:
        super().__init__(
            "google_drive_payload_mismatch",
            detail,
            status_code=409,
            retryable=False,
            category="validation",
        )


class DriveNativeEditNotSupportedError(AppError):
    def __init__(self, detail: str = "Native Google Workspace editing is not supported") -> None:
        super().__init__(
            "google_drive_native_edit_not_supported",
            detail,
            status_code=400,
            retryable=False,
            category="validation",
        )


class DriveExportNotSupportedError(AppError):
    def __init__(self, detail: str = "Requested export format is not supported") -> None:
        super().__init__(
            "google_drive_export_not_supported",
            detail,
            status_code=400,
            retryable=False,
            category="validation",
        )


class DriveContentTooLargeError(AppError):
    def __init__(self, detail: str = "Drive content exceeds the supported size limit") -> None:
        super().__init__(
            "google_drive_content_too_large",
            detail,
            status_code=413,
            retryable=False,
            category="validation",
        )


class ApprovalRequiredError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            "approval_required",
            detail,
            status_code=403,
            retryable=False,
            category="approval",
        )


class OriginNotAllowedError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            "origin_not_allowed",
            detail,
            status_code=403,
            retryable=False,
            category="security",
        )
