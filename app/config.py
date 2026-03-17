from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional, cast
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int = Field(default=8000, validation_alias="APP_PORT")
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
    rate_limit_rpm: int = Field(default=120, validation_alias="RATE_LIMIT_RPM")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_json: bool = Field(default=False, validation_alias="LOG_JSON")
    require_explicit_approval: bool = Field(default=False, validation_alias="REQUIRE_EXPLICIT_APPROVAL")
    approval_required_tools: str = Field(
        default=(
            "gmail_send_email,"
            "gmail_confirm_send_email,"
            "gmail_delete_message,"
            "calendar_delete_event,"
            "calendar_confirm_delete_event,"
            "tasks_delete_task,"
            "tasks_delete_tasklist,"
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
        default="0.1.0",
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
    google_api_max_retries: int = Field(default=3, validation_alias="GOOGLE_API_MAX_RETRIES")
    google_api_retry_base_delay_seconds: float = Field(
        default=1.0,
        validation_alias="GOOGLE_API_RETRY_BASE_DELAY_SECONDS",
    )
    google_api_retry_max_delay_seconds: float = Field(
        default=8.0,
        validation_alias="GOOGLE_API_RETRY_MAX_DELAY_SECONDS",
    )
    drive_inline_content_limit_bytes: int = Field(
        default=262144,
        validation_alias="DRIVE_INLINE_CONTENT_LIMIT_BYTES",
    )
    drive_confirmation_ttl_seconds: int = Field(
        default=600,
        validation_alias="DRIVE_CONFIRMATION_TTL_SECONDS",
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
    jwt_jwks_url: Optional[str] = Field(default=None, validation_alias="JWT_JWKS_URL")
    jwt_public_key: Optional[str] = Field(default=None, validation_alias="JWT_PUBLIC_KEY")
    jwt_shared_secret: Optional[str] = Field(default=None, validation_alias="JWT_SHARED_SECRET")
    jwt_test_mode: bool = Field(default=False, validation_alias="JWT_TEST_MODE")
    jwt_test_token: str = Field(default="local-dev-token", validation_alias="JWT_TEST_TOKEN")
    jwt_test_subject: str = Field(
        default="local-dev-user",
        validation_alias="JWT_TEST_SUBJECT",
    )

    @property
    def environment(self) -> Literal["development", "staging", "production"]:
        env = self.app_env.lower()
        if env in {"development", "staging", "production"}:
            return cast(Literal["development", "staging", "production"], env)
        return "development"

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
