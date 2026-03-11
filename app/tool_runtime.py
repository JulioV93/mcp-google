from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from app.db.session import SessionLocal
from app.config import get_settings
from app.errors import ApprovalRequiredError, AppError, ProviderError
from app.services.audit_service import AuditService


@contextmanager
def tool_session():
    with SessionLocal() as session:
        yield session


def audited_call(
    *,
    external_subject: str,
    tenant_id: str | None,
    tool_name: str,
    provider: str,
    resource_type: str,
    arguments: dict[str, object],
    operation: Callable[[Any], dict[str, object]],
) -> dict[str, object]:
    with SessionLocal() as session:
        audit_service = AuditService(session)
        try:
            result = operation(session)
            audit_service.record_tool_call(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tool_name=tool_name,
                provider=provider,
                resource_type=resource_type,
                arguments=arguments,
                result_status="success",
            )
            return result
        except AppError as exc:
            audit_service.record_tool_call(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tool_name=tool_name,
                provider=provider,
                resource_type=resource_type,
                arguments=arguments,
                result_status="error",
                error_code=exc.code,
            )
            raise
        except Exception as exc:
            audit_service.record_tool_call(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tool_name=tool_name,
                provider=provider,
                resource_type=resource_type,
                arguments=arguments,
                result_status="error",
                error_code=exc.__class__.__name__,
            )
            raise ProviderError(str(exc)) from exc


def ensure_tool_approval(*, tool_name: str, approved_tools: tuple[str, ...]) -> None:
    settings = get_settings()
    if not settings.require_explicit_approval:
        return
    if tool_name not in settings.approval_required_tool_list:
        return
    if tool_name in approved_tools:
        return
    raise ApprovalRequiredError(f"Tool '{tool_name}' requires explicit approval")
