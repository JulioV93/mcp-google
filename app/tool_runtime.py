from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.config import get_settings
from app.db.session import SessionLocal
from app.errors import AppError, ApprovalRequiredError, InternalError
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


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
            audit_service.safe_record_tool_call(
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
            session.rollback()
            audit_service.safe_record_tool_call(
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
        except Exception as exc:  # noqa: BLE001 - boundary prevents leakage or repetition of external writes
            session.rollback()
            logger.error("Unexpected tool failure (%s, %s)", tool_name, type(exc).__name__)
            audit_service.safe_record_tool_call(
                external_subject=external_subject,
                tenant_id=tenant_id,
                tool_name=tool_name,
                provider=provider,
                resource_type=resource_type,
                arguments=arguments,
                result_status="error",
                error_code="internal_error",
            )
            raise InternalError(metadata={"tool_name": tool_name}) from None
        finally:
            for client in session.info.pop("google_clients", {}).values():
                try:
                    client.close()
                except Exception:  # noqa: BLE001 - cleanup must not change a completed write outcome
                    logger.error("Google transport cleanup failed")


def ensure_tool_approval(*, tool_name: str, approved_tools: tuple[str, ...]) -> None:
    settings = get_settings()
    if not settings.require_explicit_approval:
        return
    if tool_name not in settings.approval_required_tool_list:
        return
    if tool_name in approved_tools:
        return
    raise ApprovalRequiredError(f"Tool '{tool_name}' requires explicit approval")
