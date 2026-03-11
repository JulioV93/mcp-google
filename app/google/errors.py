from __future__ import annotations

from googleapiclient.errors import HttpError

from app.errors import AuthenticationProviderError, NotFoundProviderError, PermissionProviderError, ProviderError


def map_google_http_error(exc: HttpError) -> ProviderError:
    status_code = getattr(exc.resp, "status", None)
    detail = str(exc)

    if status_code == 401:
        return AuthenticationProviderError(detail)
    if status_code == 403:
        return PermissionProviderError(detail)
    if status_code == 404:
        return NotFoundProviderError(detail)
    return ProviderError(detail)
