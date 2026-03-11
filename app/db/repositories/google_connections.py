from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GoogleConnection


class GoogleConnectionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_user_id(self, user_id: int) -> GoogleConnection | None:
        statement = select(GoogleConnection).where(GoogleConnection.user_id == user_id)
        return self.session.scalar(statement)
