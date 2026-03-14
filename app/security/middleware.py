import logging

from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import get_settings
from app.context.request_context import reset_request_context, set_request_context
from app.errors import OriginNotAllowedError, RateLimitedError, UnauthorizedError
from app.security.jwt_auth import JWTAuthenticationError, authenticate_request
from app.security.rate_limit import InMemoryRateLimiter, RateLimitExceededError


logger = logging.getLogger(__name__)


class JWTAuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.settings = get_settings()
        self.rate_limiter = InMemoryRateLimiter(limit_per_minute=self.settings.rate_limit_rpm)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        conn = HTTPConnection(scope)

        try:
            self._validate_origin(conn, path)
        except OriginNotAllowedError as exc:
            response = JSONResponse(exc.to_dict(), status_code=exc.status_code)
            await response(scope, receive, send)
            return

        if not self._requires_auth(path):
            await self.app(scope, receive, send)
            return

        try:
            principal = authenticate_request(conn, self.settings)
        except JWTAuthenticationError as exc:
            logger.info("Rejected MCP request: %s", exc)
            error = UnauthorizedError(str(exc))
            response = JSONResponse(error.to_dict(), status_code=error.status_code)
            await response(scope, receive, send)
            return

        if self.settings.rate_limit_enabled:
            try:
                self.rate_limiter.check(principal.context.subject)
            except RateLimitExceededError as exc:
                error = RateLimitedError(str(exc))
                response = JSONResponse(error.to_dict(), status_code=error.status_code)
                await response(scope, receive, send)
                return

        scope.setdefault("state", {})
        scope["state"]["request_context"] = principal.context
        scope["state"]["auth_subject"] = principal.context.subject

        token = set_request_context(principal.context)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_request_context(token)

    def _requires_auth(self, path: str) -> bool:
        protected_paths = {
            "/oauth/google/start",
            "/oauth/google/status",
            "/oauth/google/disconnect",
        }
        return path.startswith(self.settings.mcp_path) or path in protected_paths

    def _validate_origin(self, conn: HTTPConnection, path: str) -> None:
        if not path.startswith(self.settings.mcp_path):
            return
        origin = conn.headers.get("origin")
        if not origin:
            return
        if origin not in self.settings.allowed_origin_list:
            raise OriginNotAllowedError(f"Origin '{origin}' is not allowed")
