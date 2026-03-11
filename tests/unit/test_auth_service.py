from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.services.auth_service import AuthService, AuthServiceError
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
    except AuthServiceError as exc:
        assert "client credentials" in str(exc)
    else:
        raise AssertionError("Expected AuthServiceError when Google OAuth credentials are missing")


def test_google_status_is_empty_without_connection() -> None:
    session = create_test_session()
    service = AuthService(session)

    result = service.get_google_status(external_subject="user-2")

    assert result.connected is False
    assert result.google_email is None
    assert result.scopes == []
    assert result.status is None
