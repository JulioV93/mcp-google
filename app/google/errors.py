from __future__ import annotations

from googleapiclient.errors import HttpError

from app.errors import (
    AuthenticationProviderError,
    NotFoundProviderError,
    PermissionProviderError,
    ProviderError,
    TemporaryProviderError,
)


def map_google_http_error(exc: HttpError) -> ProviderError:
    status_code = getattr(exc.resp, "status", None)
    detail = str(exc)
    metadata = {"provider": "google", "provider_status_code": status_code}

    if status_code == 401:
        return AuthenticationProviderError(detail, metadata=metadata)
    if status_code == 403:
        return PermissionProviderError(detail, metadata=metadata)
    if status_code == 404:
        return NotFoundProviderError(detail, metadata=metadata)
    if status_code == 429 or (status_code is not None and 500 <= status_code <= 599):
        return TemporaryProviderError(detail, metadata=metadata)
    return ProviderError(detail, metadata=metadata)
