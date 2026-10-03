from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal, cast
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.security.tool_policy import WRITE_TOOLS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int = Field(default=8000, ge=1, le=65535, validation_alias="APP_PORT")
    app_base_url: str = Field(
        default="http://localhost:8000",
        validation_alias="APP_BASE_URL",
    )
    database_url: str = Field(
        default="sqlite:///./data/dev.db",
        validation_alias="DATABASE_URL",
    )
    allowed_origins: str = Field(
        default="http://localhost:8000,http://127.0.0.1:8000",
        validation_alias="ALLOWED_ORIGINS",
    )
    allowed_hosts: str = Field(default="", validation_alias="ALLOWED_HOSTS")
    rate_limit_enabled: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    rate_limit_rpm: int = Field(default=120, ge=1, validation_alias="RATE_LIMIT_RPM")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_json: bool = Field(default=False, validation_alias="LOG_JSON")
    authorization_mode: Literal["server_policy", "jwt_claims"] = Field(
        default="jwt_claims", validation_alias="AUTHORIZATION_MODE"
    )
    require_explicit_approval: bool = Field(
        default=False, validation_alias="REQUIRE_EXPLICIT_APPROVAL"
    )
    approval_required_tools: str = Field(
        default=(
            "auth_google_disconnect,"
            "calendar_create_event,"
            "calendar_update_event,"
            "tasks_create_tasklist,"
            "tasks_update_tasklist,"
            "tasks_create_task,"
            "tasks_update_task,"
            "tasks_complete_task,"
            "gmail_create_draft,"
            "gmail_update_draft,"
            "gmail_delete_draft,"
            "drive_create_folder,"
            "drive_create_google_doc,"
            "drive_create_google_sheet,"
            "drive_create_google_slide,"
            "drive_create_shortcut,"
            "drive_update_metadata,"
            "drive_move_file,"
            "drive_confirm_write_google_doc,"
            "drive_confirm_write_google_sheet,"
            "gmail_confirm_send_email,"
            "gmail_delete_message,"
            "calendar_confirm_delete_event,"
            "tasks_confirm_delete_task,"
            "tasks_confirm_delete_tasklist,"
            "drive_confirm_upload,"
            "drive_confirm_save_file,"
            "drive_confirm_delete_file,"
            "drive_confirm_share_file,"
            "drive_confirm_revoke_permission"
        ),
        validation_alias="APPROVAL_REQUIRED_TOOLS",
    )
    token_encryption_key: str = Field(default="", validation_alias="TOKEN_ENCRYPTION_KEY")
    mcp_server_name: str = Field(
        default="google-mcp-server",
        validation_alias="MCP_SERVER_NAME",
    )
    mcp_server_version: str = Field(
        default="0.2.0",
        validation_alias="MCP_SERVER_VERSION",
    )
    mcp_path: str = Field(default="/mcp", validation_alias="MCP_PATH")
    google_client_id: str = Field(default="", validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", validation_alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(
        default="http://localhost:8000/oauth/google/callback",
        validation_alias="GOOGLE_REDIRECT_URI",
    )
    google_id_token_clock_skew_seconds: int = Field(
        default=10,
        validation_alias="GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS",
        ge=0,
    )
    google_oauth_scopes: str = Field(
        default=(
            "https://www.googleapis.com/auth/calendar,"
            "https://www.googleapis.com/auth/tasks,"
            "https://www.googleapis.com/auth/gmail.readonly,"
            "https://www.googleapis.com/auth/gmail.compose,"
            "https://www.googleapis.com/auth/gmail.modify,"
            "https://www.googleapis.com/auth/drive,"
            "https://www.googleapis.com/auth/documents,"
            "https://www.googleapis.com/auth/spreadsheets,"
            "openid,https://www.googleapis.com/auth/userinfo.email,"
            "https://www.googleapis.com/auth/userinfo.profile"
        ),
        validation_alias="GOOGLE_OAUTH_SCOPES",
    )
    google_api_max_retries: int = Field(
        default=3, ge=0, le=10, validation_alias="GOOGLE_API_MAX_RETRIES"
    )
    google_api_retry_base_delay_seconds: float = Field(
        default=1.0,
        validation_alias="GOOGLE_API_RETRY_BASE_DELAY_SECONDS",
        ge=0,
    )
    google_api_retry_max_delay_seconds: float = Field(
        default=8.0,
        validation_alias="GOOGLE_API_RETRY_MAX_DELAY_SECONDS",
        ge=0,
    )
    drive_inline_content_limit_bytes: int = Field(
        default=262144,
        validation_alias="DRIVE_INLINE_CONTENT_LIMIT_BYTES",
        gt=0,
    )
    drive_confirmation_ttl_seconds: int = Field(
        default=600,
        validation_alias="DRIVE_CONFIRMATION_TTL_SECONDS",
        gt=0,
    )
    jwt_issuer: str = Field(
        default="http://localhost:8000/auth/dev",
        validation_alias="JWT_ISSUER",
    )
    jwt_audience: str = Field(
        default="google-mcp-server",
        validation_alias="JWT_AUDIENCE",
    )
    jwt_algorithms: str = Field(default="HS256,RS256", validation_alias="JWT_ALGORITHMS")
    jwt_jwks_url: str | None = Field(default=None, validation_alias="JWT_JWKS_URL")
    jwt_public_key: str | None = Field(default=None, validation_alias="JWT_PUBLIC_KEY")
    jwt_shared_secret: str | None = Field(default=None, validation_alias="JWT_SHARED_SECRET")
    jwt_allow_non_expiring_tokens: bool = Field(
        default=False, validation_alias="JWT_ALLOW_NON_EXPIRING_TOKENS"
    )
    jwt_test_mode: bool = Field(default=False, validation_alias="JWT_TEST_MODE")
    jwt_test_token: str = Field(default="local-dev-token", validation_alias="JWT_TEST_TOKEN")
    jwt_test_subject: str = Field(
        default="local-dev-user",
        validation_alias="JWT_TEST_SUBJECT",
    )

    mcp_body_limit_bytes: int = Field(
        default=2097152, ge=1, validation_alias="MCP_BODY_LIMIT_BYTES"
    )
    google_api_timeout_seconds: float = Field(
        default=30, gt=0, validation_alias="GOOGLE_API_TIMEOUT_SECONDS"
    )

    def validate_startup(self) -> None:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        env = self.environment
        if (
            self.authorization_mode == "server_policy"
            and {"require_explicit_approval", "approval_required_tools"} & self.model_fields_set
        ):
            logging.getLogger(__name__).warning(
                "Legacy approval settings are deprecated and ignored in server_policy mode"
            )
        if self.jwt_test_mode and env != "development":
            raise ValueError("JWT_TEST_MODE is only allowed in development")
        if not self.jwt_issuer.strip() or not self.jwt_audience.strip():
            raise ValueError("JWT issuer and audience must not be empty")
        verifiers = [self.jwt_shared_secret, self.jwt_public_key, self.jwt_jwks_url]
        if sum(bool(value) for value in verifiers) != 1 and not (
            self.jwt_test_mode and not any(verifiers)
        ):
            raise ValueError("Configure exactly one JWT verifier")
        algorithms = set(self.jwt_algorithm_list)
        if not algorithms or not algorithms <= {
            "HS256",
            "HS384",
            "HS512",
            "RS256",
            "RS384",
            "RS512",
            "ES256",
            "ES384",
            "ES512",
        }:
            raise ValueError("Unsupported JWT algorithms")
        if self.jwt_shared_secret and (
            not all(a.startswith("HS") for a in algorithms)
            or len(self.jwt_shared_secret.encode()) < 32
        ):
            raise ValueError(
                "HMAC verifier requires HS algorithms and a secret of at least 32 bytes"
            )
        if (self.jwt_public_key or self.jwt_jwks_url) and any(
            a.startswith("HS") for a in algorithms
        ):
            raise ValueError("Public-key verifier cannot use HMAC algorithms")
        if self.jwt_public_key:
            from cryptography.hazmat.primitives.asymmetric import ec, rsa

            key = load_pem_public_key(self.jwt_public_key.encode())
            family = (
                "RS"
                if isinstance(key, rsa.RSAPublicKey)
                else "ES"
                if isinstance(key, ec.EllipticCurvePublicKey)
                else ""
            )
            if not family or any(not a.startswith(family) for a in algorithms):
                raise ValueError("JWT algorithms do not match the public key")
        Fernet(self.token_encryption_key.encode("ascii"))
        if env != "development":
            for value in [self.app_base_url, self.google_redirect_uri, self.jwt_jwks_url]:
                if value and (urlparse(value).scheme != "https" or not urlparse(value).hostname):
                    raise ValueError("OAuth and JWKS URLs require HTTPS outside development")
        if env == "production":
            if self.authorization_mode == "jwt_claims" and (
                not self.require_explicit_approval
                or not WRITE_TOOLS <= set(self.approval_required_tool_list)
            ):
                raise ValueError("Production requires approval for every write tool")
            if (
                not self.rate_limit_enabled
                or not self.allowed_host_list
                or "*" in self.allowed_host_list
            ):
                raise ValueError("Production requires rate limiting and explicit trusted hosts")
        if not self.mcp_path.startswith("/") or self.mcp_path == "/":
            raise ValueError("MCP_PATH must be an absolute non-root path")
        if (
            not self.google_client_id
            or not self.google_client_secret
            or not self.google_oauth_scope_list
        ):
            raise ValueError("Google OAuth credentials and scopes are required")

    @property
    def environment(self) -> Literal["development", "staging", "production"]:
        env = self.app_env.lower()
        if env in {"development", "staging", "production"}:
            return cast(Literal["development", "staging", "production"], env)
        raise ValueError("APP_ENV must be development, staging or production")

    @property
    def jwt_algorithm_list(self) -> list[str]:
        return [item.strip() for item in self.jwt_algorithms.split(",") if item.strip()]

    @property
    def google_oauth_scope_list(self) -> list[str]:
        return [item.strip() for item in self.google_oauth_scopes.split(",") if item.strip()]

    @property
    def allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    @property
    def approval_required_tool_list(self) -> list[str]:
        return [item.strip() for item in self.approval_required_tools.split(",") if item.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        explicit = [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]
        if explicit:
            return explicit
        if self.environment == "development":
            return ["localhost", "127.0.0.1", "testserver"]
        parsed = urlparse(self.app_base_url)
        if parsed.hostname:
            return [parsed.hostname]
        return []


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
