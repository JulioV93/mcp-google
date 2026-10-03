import logging

from starlette.concurrency import run_in_threadpool
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import get_settings
from app.context.request_context import reset_request_context, set_request_context
from app.db.session import SessionLocal
from app.errors import (
    AppError,
    InternalError,
    OriginNotAllowedError,
    RateLimitedError,
    UnauthorizedError,
)
from app.security.authorization import ensure_active_identity
from app.security.jwt_auth import (
    JWTAuthenticationError,
    JWTProviderUnavailableError,
    authenticate_request,
)
from app.security.rate_limit import InMemoryRateLimiter, RateLimitExceededError
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


def check_identity_access(context) -> None:
    with SessionLocal() as session:
        try:
            ensure_active_identity(session, subject=context.subject, tenant_id=context.tenant_id)
        except AppError as exc:
            AuditService(session).safe_record_tool_call(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                tool_name="authenticated_access",
                provider="google",
                resource_type="authorization",
                arguments={},
                result_status="error",
                error_code=exc.code,
            )
            raise


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
            principal = await run_in_threadpool(authenticate_request, conn, self.settings)
        except JWTAuthenticationError as exc:
            logger.info("Rejected MCP request: %s", exc)
            error = UnauthorizedError(str(exc))
            response = JSONResponse(error.to_dict(), status_code=error.status_code)
            await response(scope, receive, send)
            return

        except JWTProviderUnavailableError:
            error = AppError(
                "auth_provider_unavailable",
                "JWT key provider is unavailable",
                status_code=503,
                retryable=True,
                category="auth",
            )
            await JSONResponse(error.to_dict(), status_code=503)(scope, receive, send)
            return

        try:
            await run_in_threadpool(check_identity_access, principal.context)
        except AppError as exc:
            await JSONResponse(exc.to_dict(), status_code=exc.status_code)(scope, receive, send)
            return
        except Exception:  # noqa: BLE001 - authorization must fail closed without leaking database details
            logger.error("Could not resolve identity authorization")
            error = InternalError()
            await JSONResponse(error.to_dict(), status_code=500)(scope, receive, send)
            return

        if self.settings.rate_limit_enabled:
            try:
                self.rate_limiter.check(
                    (principal.context.tenant_id or "", principal.context.subject)
                )
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


class MCPBodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        settings = get_settings()
        self.limit = settings.mcp_body_limit_bytes
        self.path = settings.mcp_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or not scope.get("path", "").startswith(self.path)
            or scope.get("method") not in {"POST", "PUT", "PATCH"}
        ):
            await self.app(scope, receive, send)
            return
        connection = HTTPConnection(scope)
        length = connection.headers.get("content-length")
        try:
            if length is not None and int(length) < 0:
                raise ValueError
            oversized = length is not None and int(length) > self.limit
        except ValueError:
            await JSONResponse({"error": "invalid_content_length"}, status_code=400)(
                scope, receive, send
            )
            return
        body = bytearray()
        while not oversized:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.limit:
                oversized = True
                break
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        if oversized:
            await JSONResponse({"error": "request_body_too_large"}, status_code=413)(
                scope, receive, send
            )
            return
        delivered = False

        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)
