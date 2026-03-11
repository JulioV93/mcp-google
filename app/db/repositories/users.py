from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_external_subject(self, external_subject: str) -> User | None:
        statement = select(User).where(User.external_subject == external_subject)
        return self.session.scalar(statement)

    def create(self, external_subject: str, tenant_id: str | None = None) -> User:
        user = User(external_subject=external_subject, tenant_id=tenant_id)
        self.session.add(user)
        self.session.flush()
        return user

    def get_or_create(self, external_subject: str, tenant_id: str | None = None) -> User:
        user = self.get_by_external_subject(external_subject)
        if user is not None:
            if tenant_id is not None and user.tenant_id != tenant_id:
                user.tenant_id = tenant_id
                self.session.flush()
            return user
        return self.create(external_subject=external_subject, tenant_id=tenant_id)
