from pydantic import BaseModel, ConfigDict


class AuthGoogleBeginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_url: str
    state: str
    expires_at: str
    scopes: list[str]


class AuthGoogleStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connected: bool
    google_email: str | None
    scopes: list[str]
    status: str | None
    missing_scopes: list[str]
    status_detail: str | None
    recommended_action: str | None


class AuthGoogleDisconnectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disconnected: bool
