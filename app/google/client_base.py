from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.google.credentials import GoogleCredentialsProvider
from app.google.errors import execute_google_media_request, execute_google_request


class GoogleApiClientBase:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.credentials_provider = GoogleCredentialsProvider(session, self.settings)

    def _execute(self, request: Any) -> Any:
        return execute_google_request(
            request,
            max_retries=self.settings.google_api_max_retries,
            base_delay_seconds=self.settings.google_api_retry_base_delay_seconds,
            max_delay_seconds=self.settings.google_api_retry_max_delay_seconds,
        )

    def _execute_operation(self, operation: Any) -> Any:
        return execute_google_media_request(
            operation,
            max_retries=self.settings.google_api_max_retries,
            base_delay_seconds=self.settings.google_api_retry_base_delay_seconds,
            max_delay_seconds=self.settings.google_api_retry_max_delay_seconds,
        )
