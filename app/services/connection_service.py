from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import GoogleConnection, User
from app.db.repositories.google_connections import GoogleConnectionRepository
from app.db.repositories.users import UserRepository


class ConnectionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.connections = GoogleConnectionRepository(session)

    def get_or_create_user(self, *, external_subject: str, tenant_id: str | None = None) -> User:
        return self.users.get_or_create(external_subject=external_subject, tenant_id=tenant_id)

    def get_google_connection(self, *, user: User) -> GoogleConnection | None:
        return self.connections.get_by_user_id(user.id)
