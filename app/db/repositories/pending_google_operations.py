from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import PendingGoogleOperation


class PendingGoogleOperationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        user_id: int,
        provider: str,
        operation_key: str,
        operation_type: str,
        resource_type: str,
        payload_normalized: dict[str, object],
        payload_hash: str,
        expires_at: datetime,
        resource_id: str | None = None,
        resource_name: str | None = None,
    ) -> PendingGoogleOperation:
        record = PendingGoogleOperation(
            user_id=user_id,
            provider=provider,
            operation_key=operation_key,
            operation_type=operation_type,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            payload_normalized=payload_normalized,
            payload_hash=payload_hash,
            status="pending",
            expires_at=expires_at,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_by_operation_key(self, operation_key: str) -> PendingGoogleOperation | None:
        statement = select(PendingGoogleOperation).where(
            PendingGoogleOperation.operation_key == operation_key
        )
        return self.session.scalar(statement)

    def mark_confirmed(self, record: PendingGoogleOperation) -> PendingGoogleOperation:
        record.status = "confirmed"
        record.payload_encrypted = None
        record.payload_hash = ""
        record.resource_name = None
        record.confirmed_at = datetime.now(UTC)
        self.session.flush()
        return record

    def mark_expired(self, record: PendingGoogleOperation) -> PendingGoogleOperation:
        self.session.execute(
            update(PendingGoogleOperation)
            .where(
                PendingGoogleOperation.id == record.id,
                PendingGoogleOperation.status == "pending",
                PendingGoogleOperation.expires_at <= datetime.now(UTC),
            )
            .values(status="expired", payload_encrypted=None, payload_hash="", resource_name=None)
            .execution_options(synchronize_session="fetch")
        )
        return record

    def claim(self, record: PendingGoogleOperation) -> bool:
        result = self.session.execute(
            update(PendingGoogleOperation)
            .where(
                PendingGoogleOperation.id == record.id,
                PendingGoogleOperation.user_id == record.user_id,
                PendingGoogleOperation.operation_type == record.operation_type,
                PendingGoogleOperation.status == "pending",
                PendingGoogleOperation.expires_at > datetime.now(UTC),
            )
            .values(status="executing")
            .execution_options(synchronize_session="fetch")
        )
        self.session.commit()
        return result.rowcount == 1
