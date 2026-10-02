"""Unit tests always use disposable credentials and a disposable SQLite database."""

import atexit
import os
from tempfile import TemporaryDirectory

from cryptography.fernet import Fernet

from app.config import Settings

_database = TemporaryDirectory(prefix="mcp-google-test-")
atexit.register(_database.cleanup)
os.environ.update(
    APP_ENV="development",
    APP_BASE_URL="http://localhost:8000",
    DATABASE_URL=f"sqlite:///{_database.name}/tests.db",
    ALLOWED_HOSTS="",
    ALLOWED_ORIGINS="http://localhost:8000,http://127.0.0.1:8000",
    TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),
    JWT_ALLOW_NON_EXPIRING_TOKENS="false",
    JWT_TEST_MODE="true",
    JWT_TEST_TOKEN="local-dev-token",
    JWT_TEST_SUBJECT="local-dev-user",
    JWT_ISSUER="http://localhost:8000/auth/dev",
    JWT_AUDIENCE="google-mcp-server",
    JWT_ALGORITHMS="HS256",
    JWT_SHARED_SECRET="test-only-signing-secret-at-least-32-bytes",
    JWT_JWKS_URL="",
    JWT_PUBLIC_KEY="",
    GOOGLE_CLIENT_ID="test-client.apps.googleusercontent.com",
    GOOGLE_CLIENT_SECRET="test-only-not-a-real-secret",
    REQUIRE_EXPLICIT_APPROVAL="false",
    APPROVAL_REQUIRED_TOOLS=Settings.model_fields["approval_required_tools"].default,
    GOOGLE_OAUTH_SCOPES=Settings.model_fields["google_oauth_scopes"].default,
)

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.session import engine

Base.metadata.create_all(engine)
