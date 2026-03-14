from __future__ import annotations

from datetime import UTC, datetime, timedelta
import secrets

from sqlalchemy.orm import Session

from app.db.models import OAuthState, User
from app.db.repositories.oauth_states import OAuthStateRepository


class OAuthStateStore:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = OAuthStateRepository(session)

    def create(self, *, user: User, provider: str, requested_scopes: list[str]) -> OAuthState:
        state = OAuthState(
            user_id=user.id,
            provider=provider,
            state=secrets.token_urlsafe(32),
            code_verifier=secrets.token_urlsafe(64),
            requested_scopes=requested_scopes,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
        self.session.add(state)
        self.session.flush()
        return state

    def get_valid(self, state_value: str) -> OAuthState | None:
        state = self.repository.get_by_state(state_value)
        if state is None:
            return None
        expires_at = state.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            return None
        return state

    def delete(self, state: OAuthState) -> None:
        self.session.delete(state)
        self.session.flush()
