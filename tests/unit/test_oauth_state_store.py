from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import OAuthState, User
from app.oauth.state_store import OAuthStateStore


def create_test_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", future=True, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    return session_factory()


def test_get_valid_accepts_unexpired_sqlite_state() -> None:
    session = create_test_session()
    user = User(external_subject="user-1")
    session.add(user)
    session.flush()
    state = OAuthState(
        user_id=user.id,
        provider="google",
        state="state-1",
        code_verifier="verifier-1",
        requested_scopes=["openid"],
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    session.add(state)
    session.commit()

    store = OAuthStateStore(session)

    result = store.get_valid("state-1")

    assert result is not None
    assert result.state == "state-1"


def test_get_valid_accepts_unexpired_naive_state_from_sqlite() -> None:
    session = create_test_session()
    user = User(external_subject="user-2")
    session.add(user)
    session.flush()
    state = OAuthState(
        user_id=user.id,
        provider="google",
        state="state-2",
        code_verifier="verifier-2",
        requested_scopes=["openid"],
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).replace(tzinfo=None),
    )
    session.add(state)
    session.commit()

    store = OAuthStateStore(session)

    result = store.get_valid("state-2")

    assert result is not None
    assert result.state == "state-2"
