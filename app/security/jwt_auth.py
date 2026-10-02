import logging
from dataclasses import dataclass
from functools import lru_cache

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientConnectionError, PyJWKClientError
from starlette.requests import HTTPConnection

from app.config import Settings, get_settings
from app.context.request_context import RequestContext

logger = logging.getLogger(__name__)


class JWTProviderUnavailableError(Exception):
    """JWKS unavailable; authentication remains closed."""


@lru_cache(maxsize=8)
def jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, timeout=10)


class JWTAuthenticationError(Exception):
    """Raised when JWT authentication fails."""


@dataclass(slots=True)
class AuthenticatedPrincipal:
    context: RequestContext
    raw_token: str


def extract_bearer_token(conn: HTTPConnection) -> str:
    authorization = conn.headers.get("authorization")
    if not authorization:
        raise JWTAuthenticationError("Missing Authorization header")

    try:
        scheme, token = authorization.split(" ", 1)
    except ValueError as exc:
        raise JWTAuthenticationError("Invalid Authorization header format") from exc

    if scheme.lower() != "bearer" or not token:
        raise JWTAuthenticationError("Authorization header must use Bearer token")

    return token.strip()


def authenticate_request(
    conn: HTTPConnection, settings: Settings | None = None
) -> AuthenticatedPrincipal:
    current_settings = settings or get_settings()
    token = extract_bearer_token(conn)

    if current_settings.environment != "development" and current_settings.jwt_test_mode:
        raise JWTAuthenticationError("Test authentication is disabled")
    if current_settings.jwt_test_mode and token == current_settings.jwt_test_token:
        claims = {
            "sub": current_settings.jwt_test_subject,
            "iss": current_settings.jwt_issuer,
            "aud": current_settings.jwt_audience,
        }
        context = build_request_context(claims, token_type="test")
        return AuthenticatedPrincipal(context=context, raw_token=token)

    claims = decode_jwt(token, current_settings)
    context = build_request_context(claims)
    return AuthenticatedPrincipal(context=context, raw_token=token)


def decode_jwt(token: str, settings: Settings) -> dict[str, object]:
    kwargs = {
        "algorithms": settings.jwt_algorithm_list,
        "audience": settings.jwt_audience,
        "issuer": settings.jwt_issuer,
        "options": {"require": ["sub", "iss", "aud", "exp"]},
    }

    try:
        if settings.jwt_jwks_url:
            signing_key = jwks_client(settings.jwt_jwks_url).get_signing_key_from_jwt(token)
            return jwt.decode(token, signing_key.key, **kwargs)

        if settings.jwt_public_key:
            return jwt.decode(token, settings.jwt_public_key, **kwargs)

        if settings.jwt_shared_secret:
            return jwt.decode(token, settings.jwt_shared_secret, **kwargs)
    except PyJWKClientConnectionError:
        raise JWTProviderUnavailableError("JWT key provider is unavailable") from None
    except (InvalidTokenError, PyJWKClientError) as exc:
        logger.warning("JWT validation failed (%s)", type(exc).__name__)
        raise JWTAuthenticationError("Invalid JWT token") from exc

    raise JWTAuthenticationError("JWT verifier is not configured")


def build_request_context(claims: dict[str, object], *, token_type: str = "jwt") -> RequestContext:
    subject = str(claims.get("sub") or "")
    issuer = str(claims.get("iss") or "")
    audience_value = claims.get("aud")
    if isinstance(audience_value, list):
        audience = ",".join(str(item) for item in audience_value)
    else:
        audience = str(audience_value or "")

    if not subject:
        raise JWTAuthenticationError("JWT token is missing subject")

    tenant = claims.get("tenant_id")
    if "tenant_id" in claims and (
        not isinstance(tenant, str) or not tenant.strip() or len(tenant) > 255
    ):
        raise JWTAuthenticationError("Invalid tenant_id claim")
    if len(subject) > 255 or not isinstance(claims.get("sub"), str):
        raise JWTAuthenticationError("Invalid subject claim")
    return RequestContext(
        user_id=subject,
        subject=subject,
        issuer=issuer,
        audience=audience,
        token_type=token_type,
        tenant_id=tenant,
        email=_optional_string(claims.get("email")),
        approvals=_approval_tuple(claims.get("approved_tools")),
        claims=claims,
    )


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    string_value = str(value).strip()
    return string_value or None


def _approval_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    string_value = str(value).strip()
    return (string_value,) if string_value else ()
