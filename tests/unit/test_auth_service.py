from __future__ import annotations

from datetime import UTC, datetime, timedelta
from google.auth.exceptions import RefreshError as GoogleRefreshError
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import GoogleConnection
from app.errors import ConfigurationError
from app.services.auth_service import AuthService
from app.security.encryption import decrypt_text, encrypt_text


def create_test_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return session_factory()


def test_encrypt_roundtrip_works_with_local_key() -> None:
    original = "super-secret-token"
    encrypted = encrypt_text(original)
    decrypted = decrypt_text(encrypted)

    assert decrypted == original


def test_begin_google_auth_requires_google_credentials() -> None:
    session = create_test_session()
    service = AuthService(session)
    service.settings.google_client_id = ""
    service.settings.google_client_secret = ""

    try:
        service.begin_google_auth(external_subject="user-1")
    except ConfigurationError as exc:
        assert "client credentials" in exc.detail
    else:
        raise AssertionError("Expected ConfigurationError when Google OAuth credentials are missing")


def test_google_status_is_empty_without_connection() -> None:
    session = create_test_session()
    service = AuthService(session)

    result = service.get_google_status(external_subject="user-2")

    assert result.connected is False
    assert result.google_email is None
    assert result.scopes == []
    assert result.status is None
    assert result.missing_scopes == service.settings.google_oauth_scope_list
    assert result.status_detail == "Google account is not connected"
    assert result.recommended_action == "Run auth_google_begin to connect a Google account."


def test_get_google_credentials_normalizes_aware_expiry_from_database() -> None:
    session = create_test_session()
    service = AuthService(session)

    user = service.connections.get_or_create_user(external_subject="user-3")
    session.add(
        GoogleConnection(
            user_id=user.id,
            google_email="user-3@example.com",
            google_subject="google-subject-3",
            status="active",
            granted_scopes=["https://www.googleapis.com/auth/calendar"],
            access_token_encrypted=encrypt_text("access-token", service.settings),
            refresh_token_encrypted=encrypt_text("refresh-token", service.settings),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    session.commit()

    with patch("app.services.auth_service.GoogleAuthRequest") as request_cls:
        credentials = service.get_google_credentials_for_user(external_subject="user-3")

    assert credentials.token == "access-token"
    assert credentials.refresh_token == "refresh-token"
    assert credentials.expiry is not None
    assert credentials.expiry.tzinfo is None
    request_cls.assert_not_called()


def test_get_google_credentials_marks_connection_reauth_required_when_refresh_token_is_invalid() -> None:
    session = create_test_session()
    service = AuthService(session)

    user = service.connections.get_or_create_user(external_subject="user-4")
    session.add(
        GoogleConnection(
            user_id=user.id,
            google_email="user-4@example.com",
            google_subject="google-subject-4",
            status="active",
            granted_scopes=["https://www.googleapis.com/auth/calendar"],
            access_token_encrypted=encrypt_text("access-token", service.settings),
            refresh_token_encrypted=encrypt_text("refresh-token", service.settings),
            expires_at=datetime.now(UTC) - timedelta(minutes=5),
        )
    )
    session.commit()

    with patch(
        "google.oauth2.credentials.Credentials.refresh",
        side_effect=GoogleRefreshError(
            "invalid_grant: Bad Request",
            {"error": "invalid_grant", "error_description": "Bad Request"},
        ),
    ):
        try:
            service.get_google_credentials_for_user(external_subject="user-4")
        except Exception as exc:
            assert getattr(exc, "code", None) == "google_consent_required"
            assert "reconnect Google auth" in getattr(exc, "detail", "")
            assert exc.metadata == {
                "provider": "google",
                "connection_status": "reauth_required",
                "error": "invalid_grant",
                "error_description": "Bad Request",
            }
        else:
            raise AssertionError("Expected google_consent_required when Google refresh token is invalid")

    connection = service.connections.get_google_connection(user=user)
    assert connection is not None
    assert connection.status == "reauth_required"


def test_get_google_credentials_rejects_non_active_connection_before_refresh() -> None:
    session = create_test_session()
    service = AuthService(session)

    user = service.connections.get_or_create_user(external_subject="user-5")
    session.add(
        GoogleConnection(
            user_id=user.id,
            google_email="user-5@example.com",
            google_subject="google-subject-5",
            status="reauth_required",
            granted_scopes=["https://www.googleapis.com/auth/drive"],
            access_token_encrypted=encrypt_text("access-token", service.settings),
            refresh_token_encrypted=encrypt_text("refresh-token", service.settings),
            expires_at=datetime.now(UTC) - timedelta(minutes=5),
        )
    )
    session.commit()

    with patch("google.oauth2.credentials.Credentials.refresh") as refresh_mock:
        try:
            service.get_google_credentials_for_user(external_subject="user-5")
        except Exception as exc:
            assert getattr(exc, "code", None) == "google_consent_required"
            assert exc.metadata == {
                "provider": "google",
                "connection_status": "reauth_required",
            }
        else:
            raise AssertionError("Expected google_consent_required for non-active Google connection")

    refresh_mock.assert_not_called()


def test_google_status_describes_reauth_required_state() -> None:
    session = create_test_session()
    service = AuthService(session)

    user = service.connections.get_or_create_user(external_subject="user-6")
    session.add(
        GoogleConnection(
            user_id=user.id,
            google_email="user-6@example.com",
            google_subject="google-subject-6",
            status="reauth_required",
            granted_scopes=["https://www.googleapis.com/auth/calendar"],
            access_token_encrypted=encrypt_text("access-token", service.settings),
            refresh_token_encrypted=encrypt_text("refresh-token", service.settings),
            expires_at=datetime.now(UTC) - timedelta(minutes=5),
        )
    )
    session.commit()

    result = service.get_google_status(external_subject="user-6")

    assert result.connected is False
    assert result.status == "reauth_required"
    assert result.status_detail == "Google authorization expired or was revoked; reconnection is required."
    assert result.recommended_action == "Run auth_google_begin to reconnect Google auth, then retry the request."
