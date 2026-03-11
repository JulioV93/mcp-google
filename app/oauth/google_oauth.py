from __future__ import annotations

from dataclasses import dataclass

from google.auth.transport.requests import Request as GoogleAuthRequest
from google_auth_oauthlib.flow import Flow
from google.oauth2 import credentials as google_credentials

from app.config import Settings, get_settings


GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"


@dataclass(slots=True)
class GoogleOAuthTokens:
    access_token: str
    refresh_token: str | None
    expiry_iso: str | None
    scopes: list[str]
    id_token: str | None


def build_client_config(settings: Settings | None = None) -> dict[str, object]:
    current_settings = settings or get_settings()
    return {
        "web": {
            "client_id": current_settings.google_client_id,
            "client_secret": current_settings.google_client_secret,
            "auth_uri": GOOGLE_AUTH_URI,
            "token_uri": GOOGLE_TOKEN_URI,
        }
    }


def create_flow(
    *,
    state: str | None = None,
    code_verifier: str | None = None,
    settings: Settings | None = None,
) -> Flow:
    current_settings = settings or get_settings()
    flow = Flow.from_client_config(
        build_client_config(current_settings),
        scopes=current_settings.google_oauth_scope_list,
        state=state,
    )
    flow.redirect_uri = current_settings.google_redirect_uri
    if code_verifier is not None:
        flow.code_verifier = code_verifier
    return flow


def build_authorization_url(
    *,
    state: str,
    code_verifier: str,
    settings: Settings | None = None,
) -> tuple[str, str]:
    flow = create_flow(state=state, code_verifier=code_verifier, settings=settings)
    authorization_url, returned_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        code_challenge_method="S256",
    )
    return authorization_url, returned_state


def exchange_code(
    *,
    state: str,
    code: str,
    code_verifier: str,
    settings: Settings | None = None,
) -> GoogleOAuthTokens:
    flow = create_flow(state=state, code_verifier=code_verifier, settings=settings)
    flow.fetch_token(code=code)
    credentials = flow.credentials
    return GoogleOAuthTokens(
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        expiry_iso=credentials.expiry.isoformat() if credentials.expiry else None,
        scopes=list(credentials.scopes or []),
        id_token=(credentials.id_token if hasattr(credentials, "id_token") else None),
    )


def build_user_credentials(
    *,
    access_token: str,
    refresh_token: str | None,
    scopes: list[str],
    settings: Settings | None = None,
) -> google_credentials.Credentials:
    current_settings = settings or get_settings()
    return google_credentials.Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=current_settings.google_client_id,
        client_secret=current_settings.google_client_secret,
        scopes=scopes,
    )


def refresh_user_credentials(credentials: google_credentials.Credentials) -> google_credentials.Credentials:
    credentials.refresh(GoogleAuthRequest())
    return credentials
