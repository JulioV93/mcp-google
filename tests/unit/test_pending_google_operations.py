from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import User
from app.db.repositories.pending_google_operations import PendingGoogleOperationRepository
from app.services.pending_operations import _preview_from_record


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


def test_preview_from_record_contains_next_action_and_identity() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()

    user = User(external_subject="user-1")
    session.add(user)
    session.commit()

    repo = PendingGoogleOperationRepository(session)
    record = repo.create(
        user_id=user.id,
        provider="google",
        operation_key="op-2",
        operation_type="calendar_delete",
        resource_type="calendar_event",
        payload_normalized={"calendar_id": "primary", "event_id": "evt-1"},
        payload_hash="hash-2",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        resource_id="evt-1",
        resource_name="Trading block",
    )

    preview = _preview_from_record(
        record,
        risk_level="high",
        summary={"action": "delete_calendar_event"},
    )

    assert preview["resource_identity"] == {
        "type": "calendar_event",
        "resource_id": "evt-1",
        "resource_name": "Trading block",
    }
    assert preview["next_suggested_actions"] == ["calendar_confirm_delete_event"]
