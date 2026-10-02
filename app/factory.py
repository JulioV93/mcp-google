import logging
from typing import Any, cast

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route

from app.config import get_settings
from app.context.request_context import maybe_get_request_context
from app.db.session import SessionLocal
from app.errors import AppError, InternalError, ValidationError
from app.logging import configure_logging
from app.mcp_server import mcp
from app.oauth.callback_page import callback_page
from app.security.middleware import JWTAuthMiddleware, MCPBodyLimitMiddleware
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.maintenance import maintenance_lifespan
from app.tool_runtime import ensure_tool_approval

logger = logging.getLogger(__name__)


def _json_error_response(error: AppError) -> JSONResponse:
    return JSONResponse(error.to_dict(), status_code=error.status_code)


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    error = ValidationError(detail) if exc.status_code == 400 else InternalError(detail)
    if exc.status_code != 400:
        error.status_code = exc.status_code
    return _json_error_response(error)


def _allowed_hosts(settings) -> list[str]:
    allowed_hosts = settings.allowed_host_list
    if allowed_hosts:
        return allowed_hosts
    return ["*"] if settings.environment == "development" else []


def create_app() -> Starlette:
    settings = get_settings()
    settings.validate_startup()
    configure_logging(settings.log_level, json_logs=settings.log_json)
    mcp_http_app = mcp.http_app(path=settings.mcp_path)

    async def healthcheck(request: Request) -> JSONResponse:
        context = maybe_get_request_context()
        return JSONResponse(
            {
                "status": "ok",
                "service": settings.mcp_server_name,
                "version": settings.mcp_server_version,
                "environment": settings.environment,
                "mcp_path": settings.mcp_path,
                "authenticated_subject": context.subject if context else None,
            }
        )

    def oauth_google_start(request: Request) -> JSONResponse:
        context = request.state.request_context
        subject = context.subject
        tenant_id = context.tenant_id

        with SessionLocal() as session:
            audit_service = AuditService(session)
            service = AuthService(session, settings)
            try:
                result = service.begin_google_auth(external_subject=subject, tenant_id=tenant_id)
            except AppError as exc:
                audit_service.safe_record_tool_call(
                    external_subject=subject,
                    tenant_id=tenant_id,
                    tool_name="oauth_google_start",
                    provider="google",
                    resource_type="oauth",
                    arguments={},
                    result_status="error",
                    error_code=exc.code,
                )
                return _json_error_response(exc)
            except Exception:  # noqa: BLE001 - boundary prevents leakage or repetition of external writes
                logger.error("Unexpected OAuth start failure")
                error = InternalError(metadata={"endpoint": "/oauth/google/start"})
                audit_service.safe_record_tool_call(
                    external_subject=subject,
                    tenant_id=tenant_id,
                    tool_name="oauth_google_start",
                    provider="google",
                    resource_type="oauth",
                    arguments={},
                    result_status="error",
                    error_code=error.code,
                )
                return _json_error_response(error)
            audit_service.safe_record_tool_call(
                external_subject=subject,
                tenant_id=tenant_id,
                tool_name="oauth_google_start",
                provider="google",
                resource_type="oauth",
                arguments={},
                result_status="success",
            )

        return JSONResponse(
            {
                "authorization_url": result.authorization_url,
                "state": result.state,
                "expires_at": result.expires_at,
                "scopes": result.scopes,
            }
        )

    def oauth_google_callback(request: Request) -> HTMLResponse:
        state = request.query_params.get("state")
        code = request.query_params.get("code")
        provider_error = request.query_params.get("error")
        if not state or (not code and not provider_error):
            return callback_page("invalid", status_code=400)

        with SessionLocal() as session:
            audit_service = AuditService(session)
            service = AuthService(session, settings)
            try:
                if provider_error:
                    service.cancel_google_auth(state=state)
                    result = "cancelled" if provider_error == "access_denied" else "error"
                    return callback_page(result, status_code=200 if result == "cancelled" else 502)
                connection = service.complete_google_auth(state=state, code=cast(str, code))
            except AppError as exc:
                audit_service.safe_record_tool_call(
                    external_subject="oauth-callback",
                    tenant_id=None,
                    tool_name="oauth_google_callback",
                    provider="google",
                    resource_type="oauth",
                    arguments={},
                    result_status="error",
                    error_code=exc.code,
                )
                result = "invalid" if isinstance(exc, ValidationError) else "error"
                return callback_page(result, status_code=exc.status_code)
            except Exception as exc:  # noqa: BLE001 - boundary prevents leakage or repetition of external writes
                # Provider exceptions can contain codes or tokens: log only their type.
                logger.error("Google OAuth callback failed (%s)", type(exc).__name__)
                audit_service.safe_record_tool_call(
                    external_subject="oauth-callback",
                    tenant_id=None,
                    tool_name="oauth_google_callback",
                    provider="google",
                    resource_type="oauth",
                    arguments={},
                    result_status="error",
                    error_code="internal_error",
                )
                return callback_page("error", status_code=500)
            audit_service.safe_record_tool_call(
                external_subject=connection.user.external_subject,
                tenant_id=connection.user.tenant_id or None,
                tool_name="oauth_google_callback",
                provider="google",
                resource_type="oauth",
                arguments={},
                result_status="success",
            )

        return callback_page("connected", email=connection.google_email)

    def oauth_google_disconnect(request: Request) -> JSONResponse:
        context = request.state.request_context
        subject = context.subject
        tenant_id = context.tenant_id

        with SessionLocal() as session:
            audit_service = AuditService(session)
            service = AuthService(session, settings)
            try:
                ensure_tool_approval(
                    tool_name="auth_google_disconnect", approved_tools=context.approvals
                )
                disconnected = service.disconnect_google(
                    external_subject=subject, tenant_id=tenant_id
                )
            except AppError as exc:
                audit_service.safe_record_tool_call(
                    external_subject=subject,
                    tenant_id=tenant_id,
                    tool_name="oauth_google_disconnect",
                    provider="google",
                    resource_type="oauth",
                    arguments={},
                    result_status="error",
                    error_code=exc.code,
                )
                return _json_error_response(exc)
            except Exception:  # noqa: BLE001 - boundary prevents leakage or repetition of external writes
                logger.error("Unexpected OAuth disconnect failure")
                error = InternalError(metadata={"endpoint": "/oauth/google/disconnect"})
                audit_service.safe_record_tool_call(
                    external_subject=subject,
                    tenant_id=tenant_id,
                    tool_name="oauth_google_disconnect",
                    provider="google",
                    resource_type="oauth",
                    arguments={},
                    result_status="error",
                    error_code=error.code,
                )
                return _json_error_response(error)
            audit_service.safe_record_tool_call(
                external_subject=subject,
                tenant_id=tenant_id,
                tool_name="oauth_google_disconnect",
                provider="google",
                resource_type="oauth",
                arguments={},
                result_status="success",
            )

        return JSONResponse({"disconnected": disconnected})

    def oauth_google_status(request: Request) -> JSONResponse:
        context = request.state.request_context
        subject = context.subject
        tenant_id = context.tenant_id

        with SessionLocal() as session:
            audit_service = AuditService(session)
            service = AuthService(session, settings)
            try:
                result = service.get_google_status(external_subject=subject, tenant_id=tenant_id)
            except AppError as exc:
                audit_service.safe_record_tool_call(
                    external_subject=subject,
                    tenant_id=tenant_id,
                    tool_name="oauth_google_status",
                    provider="google",
                    resource_type="oauth",
                    arguments={},
                    result_status="error",
                    error_code=exc.code,
                )
                return _json_error_response(exc)
            except Exception:  # noqa: BLE001 - boundary prevents leakage or repetition of external writes
                logger.error("Unexpected OAuth status failure")
                error = InternalError(metadata={"endpoint": "/oauth/google/status"})
                audit_service.safe_record_tool_call(
                    external_subject=subject,
                    tenant_id=tenant_id,
                    tool_name="oauth_google_status",
                    provider="google",
                    resource_type="oauth",
                    arguments={},
                    result_status="error",
                    error_code=error.code,
                )
                return _json_error_response(error)
            audit_service.safe_record_tool_call(
                external_subject=subject,
                tenant_id=tenant_id,
                tool_name="oauth_google_status",
                provider="google",
                resource_type="oauth",
                arguments={},
                result_status="success",
            )

        return JSONResponse(
            {
                "connected": result.connected,
                "google_email": result.google_email,
                "scopes": result.scopes,
                "status": result.status,
                "missing_scopes": result.missing_scopes,
                "status_detail": result.status_detail,
                "recommended_action": result.recommended_action,
            }
        )

    starlette_app = Starlette(
        debug=settings.environment == "development",
        lifespan=maintenance_lifespan(mcp_http_app.lifespan),
        middleware=[
            Middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts(settings)),
            Middleware(JWTAuthMiddleware),
            Middleware(MCPBodyLimitMiddleware),
        ],
        routes=[
            Route("/health", healthcheck),
            Route("/oauth/google/start", oauth_google_start),
            Route("/oauth/google/callback", oauth_google_callback),
            Route("/oauth/google/disconnect", oauth_google_disconnect, methods=["POST"]),
            Route("/oauth/google/status", oauth_google_status),
            Mount("/", app=mcp_http_app),
        ],
        exception_handlers=cast(dict[Any, Any], {HTTPException: _http_exception_handler}),
    )
    return starlette_app
