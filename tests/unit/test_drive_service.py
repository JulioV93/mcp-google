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
    DriveCreateNativeFileInput,
    DriveInlineContentInput,
    DriveListFilesInput,
    DrivePrepareDeleteFileInput,
    DrivePrepareSaveFileInput,
    DrivePrepareShareFileInput,
    DrivePrepareWriteGoogleDocInput,
    DrivePrepareWriteGoogleSheetInput,
    DrivePrepareUploadInput,
    DrivePermissionInput,
)
from app.services.drive_service import DriveService


def test_list_files_normalizes_shortcut_target_id() -> None:
    session = Mock()
    service = DriveService(session)
    service.client = Mock()
    service.client.list_files.return_value = {
        "files": [
            {
                "id": "shortcut-1",
                "name": "Shortcut",
                "mimeType": "application/vnd.google-apps.shortcut",
                "shortcutDetails": {"targetId": "target-123"},
            }
        ]
    }

    result = service.list_files(external_subject="user-1", input_data=DriveListFilesInput())

    items = result["items"]
    assert isinstance(items, list)
    assert items[0]["shortcut_target_id"] == "target-123"


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
    assert result["resource_identity"] == {"type": "drive_file_collection"}
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
    assert result["resource_identity"] == {"type": "drive_folder", "file_id": "folder-1"}
    assert result["mime_type"] == "application/vnd.google-apps.folder"


def test_create_google_doc_returns_native_document() -> None:
    session = Mock()
    service = DriveService(session)
    service.client = Mock()
    service.client.create_native_file.return_value = {
        "id": "doc-11",
        "name": "Plan semanal",
        "mimeType": "application/vnd.google-apps.document",
        "parents": ["folder-1"],
    }

    result = service.create_google_doc(
        external_subject="user-1",
        input_data=DriveCreateNativeFileInput(name="Plan semanal", parent_id="folder-1"),
    )

    assert result["id"] == "doc-11"
    assert result["mime_type"] == "application/vnd.google-apps.document"
    service.client.create_native_file.assert_called_once_with(
        external_subject="user-1",
        tenant_id=None,
        name="Plan semanal",
        mime_type="application/vnd.google-apps.document",
        parent_id="folder-1",
    )


def test_create_google_sheet_returns_native_spreadsheet() -> None:
    session = Mock()
    service = DriveService(session)
    service.client = Mock()
    service.client.create_native_file.return_value = {
        "id": "sheet-22",
        "name": "Presupuesto",
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }

    result = service.create_google_sheet(
        external_subject="user-1",
        input_data=DriveCreateNativeFileInput(name="Presupuesto"),
    )

    assert result["id"] == "sheet-22"
    assert result["mime_type"] == "application/vnd.google-apps.spreadsheet"


def test_create_google_slide_returns_native_presentation() -> None:
    session = Mock()
    service = DriveService(session)
    service.client = Mock()
    service.client.create_native_file.return_value = {
        "id": "slide-33",
        "name": "Pitch",
        "mimeType": "application/vnd.google-apps.presentation",
    }

    result = service.create_google_slide(
        external_subject="user-1",
        input_data=DriveCreateNativeFileInput(name="Pitch"),
    )

    assert result["id"] == "slide-33"
    assert result["mime_type"] == "application/vnd.google-apps.presentation"


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
    assert confirm["safety_level"] == "destructive"
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


def test_prepare_and_confirm_write_google_doc_flow() -> None:
    session = create_test_session()
    service = DriveService(session)
    service.client = Mock()
    service.client.get_file.return_value = {
        "id": "doc-1",
        "name": "Plan",
        "mimeType": "application/vnd.google-apps.document",
    }

    prepare = service.prepare_write_google_doc(
        external_subject="user-1",
        input_data=DrivePrepareWriteGoogleDocInput(file_id="doc-1", content_text="Hola mundo", mode="replace"),
    )

    operation_id = str(prepare["operation_id"])
    confirm = service.confirm_write_google_doc(
        external_subject="user-1",
        input_data=DriveConfirmOperationInput(operation_id=operation_id),
    )

    assert confirm["confirmed"] is True
    assert confirm["mode"] == "replace"
    service.client.write_google_doc.assert_called_once_with(
        external_subject="user-1",
        tenant_id=None,
        file_id="doc-1",
        content_text="Hola mundo",
        mode="replace",
    )


def test_prepare_and_confirm_write_google_sheet_flow() -> None:
    session = create_test_session()
    service = DriveService(session)
    service.client = Mock()
    service.client.get_file.return_value = {
        "id": "sheet-1",
        "name": "Datos",
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }

    prepare = service.prepare_write_google_sheet(
        external_subject="user-1",
        input_data=DrivePrepareWriteGoogleSheetInput(
            file_id="sheet-1",
            values=[["Mes", "Ventas"], ["Enero", 1000]],
            sheet_name="Hoja 1",
            start_cell="A1",
            mode="overwrite",
        ),
    )

    operation_id = str(prepare["operation_id"])
    confirm = service.confirm_write_google_sheet(
        external_subject="user-1",
        input_data=DriveConfirmOperationInput(operation_id=operation_id),
    )

    assert confirm["confirmed"] is True
    assert confirm["mode"] == "overwrite"
    service.client.write_google_sheet.assert_called_once_with(
        external_subject="user-1",
        tenant_id=None,
        file_id="sheet-1",
        values=[["Mes", "Ventas"], ["Enero", 1000]],
        sheet_name="Hoja 1",
        create_sheet_if_missing=False,
        start_cell="A1",
        mode="overwrite",
    )


def test_prepare_and_confirm_write_google_sheet_with_new_tab() -> None:
    session = create_test_session()
    service = DriveService(session)
    service.client = Mock()
    service.client.get_file.return_value = {
        "id": "sheet-2",
        "name": "Reporte",
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }

    prepare = service.prepare_write_google_sheet(
        external_subject="user-1",
        input_data=DrivePrepareWriteGoogleSheetInput(
            file_id="sheet-2",
            values=[["Fecha", "Monto"]],
            sheet_name="Resumen",
            create_sheet_if_missing=True,
            start_cell="A1",
            mode="overwrite",
        ),
    )

    operation_id = str(prepare["operation_id"])
    confirm = service.confirm_write_google_sheet(
        external_subject="user-1",
        input_data=DriveConfirmOperationInput(operation_id=operation_id),
    )

    assert confirm["confirmed"] is True
    assert confirm["sheet_name"] == "Resumen"
    assert confirm["create_sheet_if_missing"] is True
    service.client.write_google_sheet.assert_called_once_with(
        external_subject="user-1",
        tenant_id=None,
        file_id="sheet-2",
        values=[["Fecha", "Monto"]],
        sheet_name="Resumen",
        create_sheet_if_missing=True,
        start_cell="A1",
        mode="overwrite",
    )


def test_prepare_write_google_doc_rejects_non_doc_files() -> None:
    session = Mock()
    service = DriveService(session)
    service.client = Mock()
    service.client.get_file.return_value = {
        "id": "file-1",
        "name": "archivo.txt",
        "mimeType": "text/plain",
    }

    with pytest.raises(DriveNativeEditNotSupportedError):
        service.prepare_write_google_doc(
            external_subject="user-1",
            input_data=DrivePrepareWriteGoogleDocInput(file_id="file-1", content_text="Hola"),
        )


def test_prepare_write_google_sheet_rejects_non_sheet_files() -> None:
    session = Mock()
    service = DriveService(session)
    service.client = Mock()
    service.client.get_file.return_value = {
        "id": "file-2",
        "name": "presentacion",
        "mimeType": "application/vnd.google-apps.presentation",
    }

    with pytest.raises(DriveNativeEditNotSupportedError):
        service.prepare_write_google_sheet(
            external_subject="user-1",
            input_data=DrivePrepareWriteGoogleSheetInput(file_id="file-2", values=[["Hola"]]),
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
    assert result["safety_level"] == "destructive"
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
    assert result["safety_level"] == "destructive"
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
