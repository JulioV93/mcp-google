from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import GoogleConnection, User
from app.oauth.google_oauth import GoogleOAuthTokens, build_authorization_url, build_user_credentials, exchange_code
from app.oauth.state_store import OAuthStateStore
from app.security.encryption import decrypt_text, encrypt_text
from app.services.connection_service import ConnectionService


class AuthServiceError(Exception):
    """Raised for authentication workflow errors."""


@dataclass(slots=True)
class AuthBeginResult:
    authorization_url: str
    state: str
    expires_at: str
    scopes: list[str]


@dataclass(slots=True)
class AuthStatusResult:
    connected: bool
    google_email: str | None
    scopes: list[str]
    status: str | None


class AuthService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.state_store = OAuthStateStore(session)
        self.connections = ConnectionService(session)

    def begin_google_auth(self, *, external_subject: str, tenant_id: str | None = None) -> AuthBeginResult:
        self._validate_google_oauth_settings()
        user = self.connections.get_or_create_user(external_subject=external_subject, tenant_id=tenant_id)
        state_record = self.state_store.create(
            user=user,
            provider="google",
            requested_scopes=self.settings.google_oauth_scope_list,
        )
        authorization_url, _ = build_authorization_url(
            state=state_record.state,
            code_verifier=state_record.code_verifier,
            settings=self.settings,
        )
        self.session.commit()
        return AuthBeginResult(
            authorization_url=authorization_url,
            state=state_record.state,
            expires_at=state_record.expires_at.isoformat(),
            scopes=state_record.requested_scopes,
        )

    def complete_google_auth(self, *, state: str, code: str) -> GoogleConnection:
        self._validate_google_oauth_settings()
        state_record = self.state_store.get_valid(state)
        if state_record is None:
            raise AuthServiceError("OAuth state is invalid or expired")

        tokens = exchange_code(
            state=state_record.state,
            code=code,
            code_verifier=state_record.code_verifier,
            settings=self.settings,
        )
        user = state_record.user
        google_email, google_subject = self._extract_google_identity(tokens)
        connection = self._upsert_google_connection(user=user, tokens=tokens, google_email=google_email, google_subject=google_subject)
        self.state_store.delete(state_record)
        self.session.commit()
        return connection

    def get_google_status(self, *, external_subject: str, tenant_id: str | None = None) -> AuthStatusResult:
        user = self.connections.get_or_create_user(external_subject=external_subject, tenant_id=tenant_id)
        connection = self.connections.get_google_connection(user=user)
        self.session.commit()
        if connection is None:
            return AuthStatusResult(connected=False, google_email=None, scopes=[], status=None)
        return AuthStatusResult(
            connected=connection.status == "active",
            google_email=connection.google_email,
            scopes=list(connection.granted_scopes or []),
            status=connection.status,
        )

    def disconnect_google(self, *, external_subject: str, tenant_id: str | None = None) -> bool:
        user = self.connections.get_or_create_user(external_subject=external_subject, tenant_id=tenant_id)
        connection = self.connections.get_google_connection(user=user)
        if connection is None:
            self.session.commit()
            return False
        self.session.delete(connection)
        self.session.commit()
        return True

    def get_google_credentials_for_user(self, *, external_subject: str, tenant_id: str | None = None):
        user = self.connections.get_or_create_user(external_subject=external_subject, tenant_id=tenant_id)
        connection = self.connections.get_google_connection(user=user)
        if connection is None:
            raise AuthServiceError("Google connection is missing")

        access_token = decrypt_text(connection.access_token_encrypted, self.settings)
        refresh_token = (
            decrypt_text(connection.refresh_token_encrypted, self.settings)
            if connection.refresh_token_encrypted
            else None
        )
        credentials = build_user_credentials(
            access_token=access_token,
            refresh_token=refresh_token,
            scopes=list(connection.granted_scopes or []),
            settings=self.settings,
        )
        if connection.expires_at is not None:
            credentials.expiry = connection.expires_at
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(GoogleAuthRequest())
            connection.access_token_encrypted = encrypt_text(credentials.token, self.settings)
            if credentials.refresh_token:
                connection.refresh_token_encrypted = encrypt_text(credentials.refresh_token, self.settings)
            connection.expires_at = credentials.expiry
            self.session.commit()
        return credentials

    def _upsert_google_connection(
        self,
        *,
        user: User,
        tokens: GoogleOAuthTokens,
        google_email: str,
        google_subject: str,
    ) -> GoogleConnection:
        existing = self.connections.get_google_connection(user=user)
        if existing is None:
            existing = GoogleConnection(
                user_id=user.id,
                google_email=google_email,
                google_subject=google_subject,
                status="active",
                granted_scopes=tokens.scopes,
                access_token_encrypted=encrypt_text(tokens.access_token, self.settings),
                refresh_token_encrypted=(
                    encrypt_text(tokens.refresh_token, self.settings) if tokens.refresh_token else None
                ),
                expires_at=_parse_expiry(tokens.expiry_iso),
            )
            self.session.add(existing)
            self.session.flush()
            return existing

        existing.google_email = google_email
        existing.google_subject = google_subject
        existing.status = "active"
        existing.granted_scopes = tokens.scopes
        existing.access_token_encrypted = encrypt_text(tokens.access_token, self.settings)
        existing.refresh_token_encrypted = (
            encrypt_text(tokens.refresh_token, self.settings) if tokens.refresh_token else existing.refresh_token_encrypted
        )
        existing.expires_at = _parse_expiry(tokens.expiry_iso)
        self.session.flush()
        return existing

    def _extract_google_identity(self, tokens: GoogleOAuthTokens) -> tuple[str, str]:
        if not tokens.id_token:
            raise AuthServiceError("Google ID token was not returned")
        info = id_token.verify_oauth2_token(
            tokens.id_token,
            GoogleAuthRequest(),
            self.settings.google_client_id,
            clock_skew_in_seconds=self.settings.google_id_token_clock_skew_seconds,
        )
        google_email = str(info.get("email") or "")
        google_subject = str(info.get("sub") or "")
        email_verified = bool(info.get("email_verified", False))
        if not google_email or not google_subject:
            raise AuthServiceError("Google identity payload is incomplete")
        if not email_verified:
            raise AuthServiceError("Google identity email is not verified")
        return google_email, google_subject

    def _validate_google_oauth_settings(self) -> None:
        if not self.settings.google_client_id or not self.settings.google_client_secret:
            raise AuthServiceError("Google OAuth client credentials are not configured")


def _parse_expiry(expiry_iso: str | None) -> datetime | None:
    if not expiry_iso:
        return None
    return datetime.fromisoformat(expiry_iso)
