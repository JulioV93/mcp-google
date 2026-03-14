from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.errors import (
    DriveContentTooLargeError,
    DriveNativeEditNotSupportedError,
    DriveOperationExpiredError,
)
from app.schemas.drive import (
    DriveConfirmOperationInput,
    DriveCreateFolderInput,
    DriveInlineContentInput,
    DriveListFilesInput,
    DrivePrepareDeleteFileInput,
    DrivePrepareSaveFileInput,
    DrivePrepareShareFileInput,
    DrivePrepareUploadInput,
    DrivePermissionInput,
)
from app.services.drive_service import DriveService


def create_test_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return session_factory()


def test_list_files_normalizes_payload() -> None:
    session = Mock()
    service = DriveService(session)
    service.client = Mock()
    service.client.list_files.return_value = {
        "files": [
            {
                "id": "file-1",
                "name": "Spec",
                "mimeType": "text/plain",
                "parents": ["folder-1"],
                "owners": [{"displayName": "Ana", "emailAddress": "ana@example.com"}],
            }
        ],
        "nextPageToken": "next-token",
    }

    result = service.list_files(external_subject="user-1", input_data=DriveListFilesInput())

    items = result["items"]
    assert result["next_page_token"] == "next-token"
    assert isinstance(items, list)
    assert items[0]["id"] == "file-1"
    assert items[0]["owners"][0]["email_address"] == "ana@example.com"


def test_create_folder_returns_normalized_payload() -> None:
    session = Mock()
    service = DriveService(session)
    service.client = Mock()
    service.client.create_folder.return_value = {
        "id": "folder-1",
        "name": "Docs",
        "mimeType": "application/vnd.google-apps.folder",
        "parents": ["root"],
    }

    result = service.create_folder(
        external_subject="user-1",
        input_data=DriveCreateFolderInput(name="Docs", parent_id="root"),
    )

    assert result["id"] == "folder-1"
    assert result["mime_type"] == "application/vnd.google-apps.folder"


def test_prepare_and_confirm_upload_flow() -> None:
    session = create_test_session()
    service = DriveService(session)
    service.client = Mock()
    service.client.upload_file.return_value = {
        "id": "file-2",
        "name": "notes.txt",
        "mimeType": "text/plain",
        "parents": ["folder-1"],
    }

    prepare = service.prepare_upload(
        external_subject="user-1",
        input_data=DrivePrepareUploadInput(
            name="notes.txt",
            parent_id="folder-1",
            content=DriveInlineContentInput(content_text="hello", mime_type="text/plain"),
        ),
    )

    assert prepare["requires_confirmation"] is True
    operation_id = str(prepare["operation_id"])
    confirm = service.confirm_upload(
        external_subject="user-1",
        input_data=DriveConfirmOperationInput(operation_id=operation_id),
    )
    confirmed_file = confirm["file"]

    assert confirm["confirmed"] is True
    assert isinstance(confirmed_file, dict)
    assert confirmed_file["name"] == "notes.txt"
    service.client.upload_file.assert_called_once()


def test_prepare_save_rejects_google_native_files() -> None:
    session = Mock()
    service = DriveService(session)
    service.client = Mock()
    service.client.get_file.return_value = {
        "id": "doc-1",
        "name": "Plan",
        "mimeType": "application/vnd.google-apps.document",
    }

    with pytest.raises(DriveNativeEditNotSupportedError):
        service.prepare_save_file(
            external_subject="user-1",
            input_data=DrivePrepareSaveFileInput(
                file_id="doc-1",
                content=DriveInlineContentInput(content_text="new body", mime_type="text/plain"),
            ),
        )


def test_prepare_upload_enforces_size_limit() -> None:
    session = create_test_session()
    service = DriveService(session)
    service.settings.drive_inline_content_limit_bytes = 3

    with pytest.raises(DriveContentTooLargeError):
        service.prepare_upload(
            external_subject="user-1",
            input_data=DrivePrepareUploadInput(
                name="big.txt",
                content=DriveInlineContentInput(content_text="hello", mime_type="text/plain"),
            ),
        )


def test_confirm_delete_moves_to_trash_when_not_permanent() -> None:
    session = create_test_session()
    service = DriveService(session)
    service.client = Mock()
    service.client.get_file.return_value = {
        "id": "file-3",
        "name": "draft.txt",
        "mimeType": "text/plain",
    }
    service.client.trash_file.return_value = {
        "id": "file-3",
        "name": "draft.txt",
        "mimeType": "text/plain",
        "trashed": True,
    }

    prepare = service.prepare_delete_file(
        external_subject="user-1",
        input_data=DrivePrepareDeleteFileInput(file_id="file-3", permanent=False),
    )
    operation_id = str(prepare["operation_id"])
    result = service.confirm_delete_file(
        external_subject="user-1",
        input_data=DriveConfirmOperationInput(operation_id=operation_id),
    )
    deleted_file = result["file"]

    assert result["confirmed"] is True
    assert result["permanent"] is False
    assert isinstance(deleted_file, dict)
    assert deleted_file["trashed"] is True


def test_confirm_share_creates_permission() -> None:
    session = create_test_session()
    service = DriveService(session)
    service.client = Mock()
    service.client.get_file.return_value = {
        "id": "file-9",
        "name": "shared.txt",
        "mimeType": "text/plain",
    }
    service.client.create_permission.return_value = {
        "id": "perm-1",
        "type": "user",
        "role": "writer",
        "emailAddress": "team@example.com",
    }

    prepare = service.prepare_share_file(
        external_subject="user-1",
        input_data=DrivePrepareShareFileInput(
            file_id="file-9",
            permission=DrivePermissionInput(type="user", role="writer", email_address="team@example.com"),
        ),
    )
    operation_id = str(prepare["operation_id"])
    result = service.confirm_share_file(
        external_subject="user-1",
        input_data=DriveConfirmOperationInput(operation_id=operation_id),
    )
    permission = result["permission"]

    assert isinstance(permission, dict)
    assert permission["id"] == "perm-1"
    assert permission["email_address"] == "team@example.com"


def test_expired_operation_is_rejected() -> None:
    session = create_test_session()
    service = DriveService(session)
    service.client = Mock()
    prepare = service.prepare_upload(
        external_subject="user-1",
        input_data=DrivePrepareUploadInput(
            name="old.txt",
            content=DriveInlineContentInput(content_text="old", mime_type="text/plain"),
        ),
    )
    operation_id = str(prepare["operation_id"])
    record = service.pending_operations.get_by_operation_key(operation_id)
    assert record is not None
    record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.commit()

    with pytest.raises(DriveOperationExpiredError):
        service.confirm_upload(
            external_subject="user-1",
            input_data=DriveConfirmOperationInput(operation_id=operation_id),
        )
