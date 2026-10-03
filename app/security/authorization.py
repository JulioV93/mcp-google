"""Resolve authorization from persistent identity policy on every invocation."""

from sqlalchemy.orm import Session

from app.config import Settings
from app.db.repositories.users import UserRepository
from app.errors import PermissionDeniedError
from app.security.tool_policy import TOOL_POLICIES


def access_profile(session: Session, subject: str, tenant_id: str | None) -> str:
    user = UserRepository(session).get_by_external_subject(subject, tenant_id)
    if user is None:
        return "read_only"
    # Refresh even if a long-lived session has already loaded this identity.
    session.refresh(user, attribute_names=["access_profile"])
    return user.access_profile


def ensure_active_identity(session: Session, *, subject: str, tenant_id: str | None) -> str:
    profile = access_profile(session, subject, tenant_id)
    if profile not in {"read_only", "read_write"}:
        raise PermissionDeniedError(tool_name="authenticated_access", access_profile=profile)
    return profile


def authorize_tool(
    session: Session,
    *,
    settings: Settings,
    subject: str,
    tenant_id: str | None,
    tool_name: str,
    approved_tools: tuple[str, ...],
) -> None:
    profile = ensure_active_identity(session, subject=subject, tenant_id=tenant_id)
    policy = TOOL_POLICIES.get(tool_name)
    if policy is None:
        raise PermissionDeniedError(tool_name=tool_name, access_profile=profile)
    if settings.authorization_mode == "server_policy":
        if policy.kind in {"prepare", "write"} and profile != "read_write":
            raise PermissionDeniedError(tool_name=tool_name, access_profile=profile)
    else:
        from app.tool_runtime import ensure_tool_approval

        ensure_tool_approval(tool_name=tool_name, approved_tools=approved_tools)


def permissions(
    session: Session,
    *,
    settings: Settings,
    subject: str,
    tenant_id: str | None,
    approved_tools: tuple[str, ...],
) -> dict[str, object]:
    profile = ensure_active_identity(session, subject=subject, tenant_id=tenant_id)
    if settings.authorization_mode == "server_policy":
        allowed = [
            name
            for name, policy in TOOL_POLICIES.items()
            if profile == "read_write" or policy.kind in {"read", "connection"}
        ]
    else:
        allowed = [
            name
            for name in TOOL_POLICIES
            if not settings.require_explicit_approval
            or name not in settings.approval_required_tool_list
            or name in approved_tools
        ]
    return {
        "authorization_mode": settings.authorization_mode,
        "access_profile": profile,
        "allowed_tools": sorted(allowed),
        "confirmation_policy": "explicit_user_request",
    }
