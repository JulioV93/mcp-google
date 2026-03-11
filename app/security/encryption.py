from __future__ import annotations

from cryptography.fernet import Fernet

from app.config import Settings, get_settings


class EncryptionError(Exception):
    """Raised when encryption settings are invalid or unavailable."""


def _get_fernet(settings: Settings | None = None) -> Fernet:
    current_settings = settings or get_settings()
    if not current_settings.token_encryption_key:
        raise EncryptionError("TOKEN_ENCRYPTION_KEY is not configured")
    return Fernet(current_settings.token_encryption_key.encode("ascii"))


def encrypt_text(value: str, settings: Settings | None = None) -> str:
    fernet = _get_fernet(settings)
    return fernet.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_text(value: str, settings: Settings | None = None) -> str:
    fernet = _get_fernet(settings)
    return fernet.decrypt(value.encode("ascii")).decode("utf-8")
