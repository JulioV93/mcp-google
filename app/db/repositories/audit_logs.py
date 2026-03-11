from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AuditLog


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        user_id: int,
        tool_name: str,
        provider: str,
        resource_type: str,
        arguments_redacted: dict[str, object],
        result_status: str,
        error_code: str | None = None,
    ) -> AuditLog:
        log_entry = AuditLog(
            user_id=user_id,
            tool_name=tool_name,
            provider=provider,
            resource_type=resource_type,
            arguments_redacted=arguments_redacted,
            result_status=result_status,
            error_code=error_code,
        )
        self.session.add(log_entry)
        self.session.flush()
        return log_entry
