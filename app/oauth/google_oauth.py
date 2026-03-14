from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from typing import Any, cast
from urllib.parse import urlparse

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.oauth2 import credentials as google_credentials

from app.config import Settings, get_settings


GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"


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


@contextmanager
def allow_insecure_transport_for_local_dev(settings: Settings | None = None):
    current_settings = settings or get_settings()
    parsed = urlparse(current_settings.google_redirect_uri)
    is_local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    should_allow = current_settings.environment == "development" and is_local_http

    if not should_allow:
        yield
        return

    previous = os.environ.get("OAUTHLIB_INSECURE_TRANSPORT")
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)
        else:
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = previous


def exchange_code(
    *,
    state: str,
    code: str,
    code_verifier: str,
    authorization_response: str | None = None,
    settings: Settings | None = None,
) -> GoogleOAuthTokens:
    flow = create_flow(state=state, code_verifier=code_verifier, settings=settings)
    fetch_kwargs: dict[str, object] = {"include_client_id": True}
    if authorization_response is not None:
        fetch_kwargs["authorization_response"] = authorization_response
    else:
        fetch_kwargs["code"] = code
    with allow_insecure_transport_for_local_dev(settings):
        flow.fetch_token(**fetch_kwargs)
    credentials = cast(Credentials, flow.credentials)
    credential_data = cast(Any, credentials)
    id_token = credential_data.id_token if hasattr(credential_data, "id_token") else None
    access_token = credentials.token
    if access_token is None:
        raise ValueError("Google OAuth token exchange did not return an access token")
    return GoogleOAuthTokens(
        access_token=access_token,
        refresh_token=credentials.refresh_token,
        expiry_iso=credentials.expiry.isoformat() if credentials.expiry else None,
        scopes=list(credentials.scopes or []),
        id_token=(str(id_token) if id_token is not None else None),
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
