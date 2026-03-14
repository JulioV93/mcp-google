from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
import logging
from typing import Any

from app.config import get_settings
from app.db.session import SessionLocal
from app.errors import ApprovalRequiredError, AppError, InternalError
from app.services.audit_service import AuditService


logger = logging.getLogger(__name__)


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
            logger.exception("Unexpected error during tool execution", extra={"tool_name": tool_name})
            audit_service.record_tool_call(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tool_name=tool_name,
                provider=provider,
                resource_type=resource_type,
                arguments=arguments,
                result_status="error",
                error_code="internal_error",
            )
            raise InternalError(metadata={"tool_name": tool_name}) from exc


def ensure_tool_approval(*, tool_name: str, approved_tools: tuple[str, ...]) -> None:
    settings = get_settings()
    if not settings.require_explicit_approval:
        return
    if tool_name not in settings.approval_required_tool_list:
        return
    if tool_name in approved_tools:
        return
    raise ApprovalRequiredError(f"Tool '{tool_name}' requires explicit approval")
