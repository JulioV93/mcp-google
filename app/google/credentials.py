from __future__ import annotations

from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.errors import InternalError
from app.services.auth_service import AuthService


class GoogleCredentialsProvider:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.auth_service = AuthService(session, self.settings)

    def get_for_user(self, *, external_subject: str, tenant_id: str | None = None) -> Credentials:
        key = (tenant_id or "", external_subject)
        cache = self.session.info.setdefault("google_credentials", {})
        if key in cache:
            return cache[key]
        credentials = self.auth_service.get_google_credentials_for_user(
            external_subject=external_subject,
            tenant_id=tenant_id,
        )
        if not isinstance(credentials, Credentials):
            raise InternalError("Expected Google OAuth credentials")
        cache[key] = credentials
        return credentials
