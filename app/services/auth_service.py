from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial

import requests
from google.auth.exceptions import RefreshError as GoogleRefreshError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import GoogleConnection, User
from app.errors import (
    AuthenticationProviderError,
    ConfigurationError,
    ProviderError,
    ValidationError,
)
from app.oauth.google_oauth import (
    GoogleOAuthTokens,
    build_authorization_url,
    build_user_credentials,
    exchange_code,
)
from app.oauth.state_store import OAuthStateStore
from app.security.encryption import decrypt_text, encrypt_text
from app.services.connection_service import ConnectionService


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
    missing_scopes: list[str]
    status_detail: str | None
    recommended_action: str | None


class AuthService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.state_store = OAuthStateStore(session)
        self.connections = ConnectionService(session)

    def begin_google_auth(
        self, *, external_subject: str, tenant_id: str | None = None
    ) -> AuthBeginResult:
        self._validate_google_oauth_settings()
        user = self.connections.get_or_create_user(
            external_subject=external_subject, tenant_id=tenant_id
        )
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

    def complete_google_auth(
        self,
        *,
        state: str,
        code: str,
        authorization_response: str | None = None,
    ) -> GoogleConnection:
        self._validate_google_oauth_settings()
        state_record = self.state_store.consume(state)
        if state_record is None or state_record.provider != "google":
            raise ValidationError("OAuth state is invalid or expired")

        tokens = exchange_code(
            state=state_record.state,
            code=code,
            code_verifier=state_record.code_verifier,
            authorization_response=authorization_response,
            settings=self.settings,
        )
        user = state_record.user
        google_email, google_subject = self._extract_google_identity(tokens)
        connection = self._upsert_google_connection(
            user=user, tokens=tokens, google_email=google_email, google_subject=google_subject
        )
        self.session.commit()
        return connection

    def cancel_google_auth(self, *, state: str) -> None:
        state_record = self.state_store.consume(state)
        if state_record is None or state_record.provider != "google":
            raise ValidationError("OAuth state is invalid or expired")
        self.session.commit()

    def get_google_status(
        self, *, external_subject: str, tenant_id: str | None = None
    ) -> AuthStatusResult:
        user = self.connections.get_or_create_user(
            external_subject=external_subject, tenant_id=tenant_id
        )
        connection = self.connections.get_google_connection(user=user)
        self.session.commit()
        if connection is None:
            return AuthStatusResult(
                connected=False,
                google_email=None,
                scopes=[],
                status=None,
                missing_scopes=list(self.settings.google_oauth_scope_list),
                status_detail="Google account is not connected",
                recommended_action="Run auth_google_begin to connect a Google account.",
            )
        granted_scopes = list(connection.granted_scopes or [])
        missing_scopes = [
            scope for scope in self.settings.google_oauth_scope_list if scope not in granted_scopes
        ]
        status_detail, recommended_action = _describe_connection_status(connection.status)
        return AuthStatusResult(
            connected=connection.status == "active",
            google_email=connection.google_email,
            scopes=granted_scopes,
            status=connection.status,
            missing_scopes=missing_scopes,
            status_detail=status_detail,
            recommended_action=recommended_action,
        )

    def disconnect_google(self, *, external_subject: str, tenant_id: str | None = None) -> bool:
        user = self.connections.get_or_create_user(
            external_subject=external_subject, tenant_id=tenant_id
        )
        connection = self.connections.get_google_connection(user=user)
        if connection is None:
            self.session.commit()
            return False
        self.session.delete(connection)
        self.session.commit()
        return True

    def get_google_credentials_for_user(
        self, *, external_subject: str, tenant_id: str | None = None
    ):
        user = self.connections.get_or_create_user(
            external_subject=external_subject, tenant_id=tenant_id
        )
        connection = self.connections.get_google_connection(user=user)
        if connection is None:
            raise AuthenticationProviderError("Google connection is missing")
        if connection.status != "active":
            raise AuthenticationProviderError(
                "Google authorization requires reconnection",
                metadata={
                    "provider": "google",
                    "connection_status": connection.status,
                },
            )

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
            credentials.expiry = _google_auth_compatible_expiry(connection.expires_at)
        if credentials.expired and credentials.refresh_token:
            try:
                with requests.Session() as transport:
                    credentials.refresh(
                        partial(
                            GoogleAuthRequest(session=transport),
                            timeout=self.settings.google_api_timeout_seconds,
                        )
                    )
            except GoogleRefreshError as exc:
                refresh_error = _classify_google_refresh_error(exc)
                if refresh_error["error"] == "invalid_grant":
                    self._mark_connection_reauth_required(connection)
                    raise AuthenticationProviderError(
                        "Google authorization expired or was revoked; reconnect Google auth and retry",
                        metadata={
                            "provider": "google",
                            "connection_status": connection.status,
                            **refresh_error,
                        },
                    ) from None
                raise ProviderError(
                    "Unable to refresh Google credentials",
                    metadata={
                        "provider": "google",
                        **refresh_error,
                    },
                ) from None
            connection.access_token_encrypted = encrypt_text(credentials.token, self.settings)
            if credentials.refresh_token:
                connection.refresh_token_encrypted = encrypt_text(
                    credentials.refresh_token, self.settings
                )
            connection.expires_at = credentials.expiry
            self.session.commit()
        return credentials

    def _mark_connection_reauth_required(self, connection: GoogleConnection) -> None:
        connection.status = "reauth_required"
        self.session.commit()

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
                    encrypt_text(tokens.refresh_token, self.settings)
                    if tokens.refresh_token
                    else None
                ),
                expires_at=_parse_expiry(tokens.expiry_iso),
            )
            self.session.add(existing)
            self.session.flush()
            return existing

        previous_subject = existing.google_subject
        existing.google_email = google_email
        existing.google_subject = google_subject
        existing.status = "active"
        existing.granted_scopes = tokens.scopes
        existing.access_token_encrypted = encrypt_text(tokens.access_token, self.settings)
        existing.refresh_token_encrypted = (
            encrypt_text(tokens.refresh_token, self.settings)
            if tokens.refresh_token
            else existing.refresh_token_encrypted
            if previous_subject == google_subject
            else None
        )
        existing.expires_at = _parse_expiry(tokens.expiry_iso)
        self.session.flush()
        return existing

    def _extract_google_identity(self, tokens: GoogleOAuthTokens) -> tuple[str, str]:
        if not tokens.id_token:
            raise AuthenticationProviderError("Google ID token was not returned")
        with requests.Session() as transport:
            info = id_token.verify_oauth2_token(
                tokens.id_token,
                partial(
                    GoogleAuthRequest(session=transport),
                    timeout=self.settings.google_api_timeout_seconds,
                ),
                self.settings.google_client_id,
                clock_skew_in_seconds=self.settings.google_id_token_clock_skew_seconds,
            )
        google_email = str(info.get("email") or "")
        google_subject = str(info.get("sub") or "")
        email_verified = bool(info.get("email_verified", False))
        if not google_email or not google_subject:
            raise AuthenticationProviderError("Google identity payload is incomplete")
        if not email_verified:
            raise AuthenticationProviderError("Google identity email is not verified")
        return google_email, google_subject

    def _validate_google_oauth_settings(self) -> None:
        if not self.settings.google_client_id or not self.settings.google_client_secret:
            raise ConfigurationError("Google OAuth client credentials are not configured")


def _parse_expiry(expiry_iso: str | None) -> datetime | None:
    if not expiry_iso:
        return None
    return datetime.fromisoformat(expiry_iso)


def _google_auth_compatible_expiry(expiry: datetime) -> datetime:
    if expiry.tzinfo is None:
        return expiry
    return expiry.astimezone(UTC).replace(tzinfo=None)


def _classify_google_refresh_error(exc: GoogleRefreshError) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if len(exc.args) > 1 and isinstance(exc.args[1], dict):
        error_payload = exc.args[1]
        error = error_payload.get("error")
        if isinstance(error, str) and error:
            metadata["error"] = (
                error
                if error
                in {"invalid_grant", "invalid_client", "invalid_scope", "temporarily_unavailable"}
                else "refresh_failed"
            )
    if "error" not in metadata:
        metadata["error"] = "refresh_failed"
    return metadata


def _describe_connection_status(status: str | None) -> tuple[str | None, str | None]:
    if status == "active":
        return "Google account is connected and ready.", None
    if status == "reauth_required":
        return (
            "Google authorization expired or was revoked; reconnection is required.",
            "Run auth_google_begin to reconnect Google auth, then retry the request.",
        )
    if status:
        return (
            f"Google connection status is '{status}'.",
            "Check the Google connection and reconnect if needed.",
        )
    return "Google account is not connected", "Run auth_google_begin to connect a Google account."
