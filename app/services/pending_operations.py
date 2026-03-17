from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import PendingGoogleOperation
from app.db.repositories.pending_google_operations import PendingGoogleOperationRepository
from app.errors import (
    AppError,
    PendingOperationConsumedError,
    PendingOperationExpiredError,
    PendingOperationNotFoundError,
    PendingPayloadMismatchError,
)
from app.services.connection_service import ConnectionService


def _generate_operation_key() -> str:
    return secrets.token_urlsafe(24)


def _hash_payload(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _operation_expiry(ttl_seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)


def _is_expired(value: datetime) -> bool:
    current = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= current


def _preview_from_record(
    record: PendingGoogleOperation,
    *,
    risk_level: str,
    summary: dict[str, object],
) -> dict[str, object]:
    return {
        "operation_id": record.operation_key,
        "operation_type": record.operation_type,
        "resource_type": record.resource_type,
        "resource_id": record.resource_id,
        "resource_name": record.resource_name,
        "resource_identity": {
            "type": record.resource_type,
            "resource_id": record.resource_id,
            "resource_name": record.resource_name,
        },
        "expires_at": record.expires_at.isoformat(),
        "requires_confirmation": True,
        "risk_level": risk_level,
        "safety_level": "destructive" if risk_level in {"high", "critical"} else "write",
        "human_summary": f"Prepared {record.operation_type} for confirmation.",
        "next_suggested_actions": [
            _confirm_tool_name(record.operation_type),
        ],
        "summary": summary,
    }


def _get_pending_operation_record(
    *,
    session: Session,
    connections: ConnectionService,
    pending_operations: PendingGoogleOperationRepository,
    external_subject: str,
    tenant_id: str | None,
    operation_id: str,
    expected_operation_type: str,
) -> PendingGoogleOperation:
    user = connections.get_or_create_user(external_subject=external_subject, tenant_id=tenant_id)
    record = pending_operations.get_by_operation_key(operation_id)
    if record is None or record.user_id != user.id:
        raise PendingOperationNotFoundError()
    if record.operation_type != expected_operation_type:
        raise PendingOperationNotFoundError("Pending confirmation operation type does not match")
    if record.status == "confirmed":
        raise _consumed_error_for_operation(expected_operation_type)
    if record.status != "pending":
        raise PendingOperationNotFoundError("Pending confirmation operation is no longer pending")
    if _is_expired(record.expires_at):
        pending_operations.mark_expired(record)
        session.commit()
        raise _expired_error_for_operation(expected_operation_type)
    if record.payload_hash != _hash_payload(record.payload_normalized):
        raise PendingPayloadMismatchError()
    return record


def _as_str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PendingPayloadMismatchError("Expected a non-empty string value in the pending operation payload")
    return value


def _confirm_tool_name(operation_type: str) -> str:
    mapping = {
        "calendar_delete": "calendar_confirm_delete_event",
        "tasks_delete_task": "tasks_confirm_delete_task",
        "tasks_delete_tasklist": "tasks_confirm_delete_tasklist",
        "drive_upload": "drive_confirm_upload",
        "drive_save": "drive_confirm_save_file",
        "drive_write_google_doc": "drive_confirm_write_google_doc",
        "drive_write_google_sheet": "drive_confirm_write_google_sheet",
        "drive_delete": "drive_confirm_delete_file",
        "drive_share": "drive_confirm_share_file",
        "drive_revoke_permission": "drive_confirm_revoke_permission",
    }
    return mapping.get(operation_type, "confirm_operation")


def _expired_error_for_operation(operation_type: str) -> AppError:
    if operation_type.startswith("drive_"):
        from app.errors import DriveOperationExpiredError

        return DriveOperationExpiredError()
    return PendingOperationExpiredError()


def _consumed_error_for_operation(operation_type: str) -> AppError:
    if operation_type.startswith("drive_"):
        from app.errors import DriveOperationConsumedError

        return DriveOperationConsumedError()
    return PendingOperationConsumedError()
