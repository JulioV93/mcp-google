from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.repositories.users import UserRepository


def create_test_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", future=True, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    return session_factory()


def test_user_repository_get_or_create_creates_and_reuses_user() -> None:
    session = create_test_session()
    repo = UserRepository(session)

    first = repo.get_or_create("user-123", tenant_id="tenant-a")
    session.commit()

    second = repo.get_or_create("user-123", tenant_id="tenant-a")

    assert first.id == second.id
    assert second.external_subject == "user-123"
    assert second.tenant_id == "tenant-a"


def test_user_repository_isolates_tenant_from_missing_tenant() -> None:
    session = create_test_session()
    repo = UserRepository(session)

    user = repo.get_or_create("user-456")
    session.commit()

    updated = repo.get_or_create("user-456", tenant_id="tenant-b")

    assert user.id != updated.id
    assert user.tenant_id == ""
    assert updated.tenant_id == "tenant-b"
