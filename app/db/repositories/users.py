from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_external_subject(
        self, external_subject: str, tenant_id: str | None = None
    ) -> User | None:
        return self.session.scalar(
            select(User).where(
                User.external_subject == external_subject, User.tenant_id == (tenant_id or "")
            )
        )

    def create(self, external_subject: str, tenant_id: str | None = None) -> User:
        user = User(external_subject=external_subject, tenant_id=tenant_id or "")
        self.session.add(user)
        self.session.flush()
        return user

    def get_or_create(self, external_subject: str, tenant_id: str | None = None) -> User:
        user = self.get_by_external_subject(external_subject, tenant_id)
        if user is not None:
            return user
        try:
            with self.session.begin_nested():
                return self.create(external_subject, tenant_id)
        except IntegrityError:
            user = self.get_by_external_subject(external_subject, tenant_id)
            if user is None:
                raise
            return user
