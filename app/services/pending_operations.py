from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from functools import wraps

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import PendingGoogleOperation
from app.db.repositories.pending_google_operations import PendingGoogleOperationRepository
from app.errors import (
    AppError,
    OperationOutcomeUnknownError,
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
    return datetime.now(UTC) + timedelta(seconds=ttl_seconds)


def _is_expired(value: datetime) -> bool:
    current = datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
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
        "confirmation_tool": _confirm_tool_name(record.operation_type),
        "confirmation_arguments": {"operation_id": record.operation_key},
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
    if record.status == "unknown":
        raise OperationOutcomeUnknownError()
    if record.status in {"confirmed", "executing", "failed"}:
        raise _consumed_error_for_operation(expected_operation_type)
    if record.status != "pending":
        raise PendingOperationNotFoundError("Pending confirmation operation is no longer pending")
    if _is_expired(record.expires_at):
        pending_operations.mark_expired(record)
        session.commit()
        raise _expired_error_for_operation(expected_operation_type)
    if record.payload_hash != _hash_payload(record.payload_normalized):
        raise PendingPayloadMismatchError()
    if not pending_operations.claim(record):
        raise _consumed_error_for_operation(expected_operation_type)
    session.info["claimed_operation"] = record.id
    return record


def _as_str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PendingPayloadMismatchError(
            "Expected a non-empty string value in the pending operation payload"
        )
    return value


def _confirm_tool_name(operation_type: str) -> str:
    mapping = {
        "gmail_send": "gmail_confirm_send_email",
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


def create_pending_operation(service, *, external_subject, tenant_id=None, **values):
    user = service.connections.get_or_create_user(
        external_subject=external_subject, tenant_id=tenant_id
    )
    payload = values["payload_normalized"]
    record = service.pending_operations.create(
        user_id=user.id,
        provider="google",
        operation_key=_generate_operation_key(),
        payload_hash=_hash_payload(payload),
        expires_at=_operation_expiry(service.settings.drive_confirmation_ttl_seconds),
        **values,
    )
    service.session.commit()
    return record


def confirmed_operation(function):
    @wraps(function)
    def execute(service, *args, **kwargs):
        session = service.session
        try:
            return function(service, *args, **kwargs)
        except Exception as exc:
            operation_id = session.info.get("claimed_operation")
            if operation_id is None:
                raise
            session.rollback()
            # Only definitive provider rejections prove that the write did not happen.
            definitive = isinstance(exc, AppError) and exc.status_code in {400, 401, 403, 404, 412}
            try:
                result = session.execute(
                    update(PendingGoogleOperation)
                    .where(
                        PendingGoogleOperation.id == operation_id,
                        PendingGoogleOperation.status == "executing",
                    )
                    .values(
                        status="failed" if definitive else "unknown",
                        payload_encrypted=None,
                        payload_hash="",
                        resource_name=None,
                    )
                )
                session.commit()
            except Exception:  # noqa: BLE001 - boundary prevents leakage or repetition of external writes
                session.rollback()
                logging.getLogger(__name__).error("Could not persist operation outcome")
                raise OperationOutcomeUnknownError() from None
            if not result.rowcount:
                record = session.get(PendingGoogleOperation, operation_id)
                if record is not None and record.status == "confirmed":
                    logging.getLogger(__name__).error("Post-write metadata unavailable")
                    return {
                        "confirmed": True,
                        "operation_id": record.operation_key,
                        "metadata_unavailable": True,
                    }
            if not definitive and result.rowcount:
                raise OperationOutcomeUnknownError() from None
            raise
        finally:
            session.info.pop("claimed_operation", None)

    return execute
