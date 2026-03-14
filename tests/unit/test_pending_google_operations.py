from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import User
from app.db.repositories.pending_google_operations import PendingGoogleOperationRepository


def test_repository_creates_and_confirms_operation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()

    user = User(external_subject="user-1")
    session.add(user)
    session.commit()

    repo = PendingGoogleOperationRepository(session)
    repo.create(
        user_id=user.id,
        provider="google",
        operation_key="op-1",
        operation_type="drive_upload",
        resource_type="drive_file",
        payload_normalized={"name": "notes.txt"},
        payload_hash="hash-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        resource_name="notes.txt",
    )
    session.commit()

    loaded = repo.get_by_operation_key("op-1")
    assert loaded is not None
    assert loaded.resource_name == "notes.txt"
    assert loaded.status == "pending"

    repo.mark_confirmed(loaded)
    session.commit()
    assert loaded.status == "confirmed"
    assert loaded.confirmed_at is not None
