from __future__ import annotations

from typing import Any

import httplib2
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.errors import AppError, OperationOutcomeUnknownError, TemporaryProviderError
from app.google.credentials import GoogleCredentialsProvider
from app.google.errors import execute_google_media_request, execute_google_request


class GoogleApiClientBase:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.credentials_provider = GoogleCredentialsProvider(session, self.settings)

    def _get_service(
        self, api: str, version: str, *, external_subject: str, tenant_id: str | None = None
    ):
        key = (tenant_id or "", external_subject, api, version)
        clients = self.session.info.setdefault("google_clients", {})
        if key not in clients:
            credentials = self.credentials_provider.get_for_user(
                external_subject=external_subject, tenant_id=tenant_id
            )
            http = AuthorizedHttp(
                credentials,
                http=httplib2.Http(timeout=self.settings.google_api_timeout_seconds),
                max_refresh_attempts=0,
            )
            clients[key] = build(api, version, http=http, cache_discovery=False)
        return clients[key]

    def _execute(self, request: Any) -> Any:
        try:
            return execute_google_request(
                request,
                max_retries=self.settings.google_api_max_retries if request.method == "GET" else 0,
                base_delay_seconds=self.settings.google_api_retry_base_delay_seconds,
                max_delay_seconds=self.settings.google_api_retry_max_delay_seconds,
            )
        except AppError as exc:
            if request.method != "GET" and (exc.retryable or exc.status_code >= 500):
                raise OperationOutcomeUnknownError() from None
            raise
        except (OSError, httplib2.HttpLib2Error):
            if request.method != "GET":
                raise OperationOutcomeUnknownError() from None
            raise TemporaryProviderError("Google transport unavailable") from None

    def _execute_operation(self, operation: Any) -> Any:
        return execute_google_media_request(
            operation,
            max_retries=self.settings.google_api_max_retries,
            base_delay_seconds=self.settings.google_api_retry_base_delay_seconds,
            max_delay_seconds=self.settings.google_api_retry_max_delay_seconds,
        )
