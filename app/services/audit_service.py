from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.repositories.audit_logs import AuditLogRepository
from app.db.repositories.users import UserRepository
from app.logging import redact_value


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audit_logs = AuditLogRepository(session)
        self.users = UserRepository(session)

    def record_tool_call(
        self,
        *,
        external_subject: str,
        tenant_id: str | None,
        tool_name: str,
        provider: str,
        resource_type: str,
        arguments: dict[str, object],
        result_status: str,
        error_code: str | None = None,
    ) -> None:
        user = self.users.get_or_create(external_subject=external_subject, tenant_id=tenant_id)
        self.audit_logs.create(
            user_id=user.id,
            tool_name=tool_name,
            provider=provider,
            resource_type=resource_type,
            arguments_redacted=redact_value(arguments),
            result_status=result_status,
            error_code=error_code,
        )
        self.session.commit()
