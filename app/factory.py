from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from app.config import get_settings
from app.context.request_context import maybe_get_request_context
from app.db.session import SessionLocal
from app.logging import configure_logging
from app.mcp_server import mcp
from app.security.middleware import JWTAuthMiddleware
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService, AuthServiceError


def create_app() -> Starlette:
    settings = get_settings()
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

    async def oauth_google_start(request: Request) -> JSONResponse:
        context = request.state.request_context
        subject = context.subject
        tenant_id = context.tenant_id

        with SessionLocal() as session:
            audit_service = AuditService(session)
            service = AuthService(session, settings)
            try:
                result = service.begin_google_auth(external_subject=subject, tenant_id=tenant_id)
            except AuthServiceError as exc:
                audit_service.record_tool_call(
                    external_subject=subject,
                    tenant_id=tenant_id,
                    tool_name="oauth_google_start",
                    provider="google",
                    resource_type="oauth",
                    arguments={},
                    result_status="error",
                    error_code="provider_error",
                )
                return JSONResponse({"error": "provider_error", "detail": str(exc)}, status_code=400)
            audit_service.record_tool_call(
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

    async def oauth_google_callback(request: Request) -> JSONResponse:
        state = request.query_params.get("state")
        code = request.query_params.get("code")
        if not state or not code:
            return JSONResponse(
                {"error": "validation_error", "detail": "Missing code or state"},
                status_code=400,
            )

        with SessionLocal() as session:
            audit_service = AuditService(session)
            service = AuthService(session, settings)
            try:
                connection = service.complete_google_auth(state=state, code=code)
            except AuthServiceError as exc:
                audit_service.record_tool_call(
                    external_subject="oauth-callback",
                    tenant_id=None,
                    tool_name="oauth_google_callback",
                    provider="google",
                    resource_type="oauth",
                    arguments={"state": state},
                    result_status="error",
                    error_code="provider_error",
                )
                return JSONResponse({"error": "provider_error", "detail": str(exc)}, status_code=400)
            audit_service.record_tool_call(
                external_subject=connection.user.external_subject if hasattr(connection, "user") else "oauth-callback",
                tenant_id=None,
                tool_name="oauth_google_callback",
                provider="google",
                resource_type="oauth",
                arguments={"state": state},
                result_status="success",
            )

        return JSONResponse(
            {
                "connected": True,
                "google_email": connection.google_email,
                "google_subject": connection.google_subject,
                "status": connection.status,
                "scopes": connection.granted_scopes,
            }
        )

    async def oauth_google_disconnect(request: Request) -> JSONResponse:
        context = request.state.request_context
        subject = context.subject
        tenant_id = context.tenant_id

        with SessionLocal() as session:
            audit_service = AuditService(session)
            service = AuthService(session, settings)
            disconnected = service.disconnect_google(external_subject=subject, tenant_id=tenant_id)
            audit_service.record_tool_call(
                external_subject=subject,
                tenant_id=tenant_id,
                tool_name="oauth_google_disconnect",
                provider="google",
                resource_type="oauth",
                arguments={},
                result_status="success",
            )

        return JSONResponse({"disconnected": disconnected})

    async def oauth_google_status(request: Request) -> JSONResponse:
        context = request.state.request_context
        subject = context.subject
        tenant_id = context.tenant_id

        with SessionLocal() as session:
            audit_service = AuditService(session)
            service = AuthService(session, settings)
            result = service.get_google_status(external_subject=subject, tenant_id=tenant_id)
            audit_service.record_tool_call(
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
            }
        )

    starlette_app = Starlette(
        debug=settings.environment == "development",
        lifespan=mcp_http_app.lifespan,
        middleware=[
            Middleware(TrustedHostMiddleware, allowed_hosts=["*"]),
            Middleware(JWTAuthMiddleware),
        ],
        routes=[
            Route("/health", healthcheck),
            Route("/oauth/google/start", oauth_google_start),
            Route("/oauth/google/callback", oauth_google_callback),
            Route("/oauth/google/disconnect", oauth_google_disconnect, methods=["POST"]),
            Route("/oauth/google/status", oauth_google_status),
            Mount("/", app=mcp_http_app),
        ],
    )
    return starlette_app
