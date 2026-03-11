from __future__ import annotations


class AppError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class UnauthorizedError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__("unauthorized_client", detail)


class RateLimitedError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__("rate_limited", detail)


class ProviderError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__("provider_error", detail)


class AuthenticationProviderError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__("google_consent_required", detail)


class NotFoundProviderError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__("resource_not_found", detail)


class PermissionProviderError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__("insufficient_scope", detail)


class ValidationError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__("validation_error", detail)


class ApprovalRequiredError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__("approval_required", detail)


class OriginNotAllowedError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__("origin_not_allowed", detail)
