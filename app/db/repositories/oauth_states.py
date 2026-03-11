from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import OAuthState


class OAuthStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_state(self, state: str) -> OAuthState | None:
        statement = select(OAuthState).where(OAuthState.state == state)
        return self.session.scalar(statement)
