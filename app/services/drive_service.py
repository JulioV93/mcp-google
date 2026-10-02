from __future__ import annotations

import base64
import unicodedata
from difflib import SequenceMatcher
from typing import cast

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import PendingGoogleOperation
from app.db.repositories.pending_google_operations import PendingGoogleOperationRepository
from app.errors import (
    DriveContentTooLargeError,
    DriveExportNotSupportedError,
    DriveNativeEditNotSupportedError,
    ValidationError,
)
from app.google.drive_client import DriveClient, encode_bytes_to_base64
from app.schemas.drive import (
    DriveConfirmOperationInput,
    DriveCreateFolderInput,
    DriveCreateNativeFileInput,
    DriveCreateShortcutInput,
    DriveDownloadFileInput,
    DriveExportFileInput,
    DriveFindFileByNameInput,
    DriveFindFolderByNameInput,
    DriveGetFileInput,
    DriveListFilesInput,
    DriveListPermissionsInput,
    DriveMoveFileInput,
    DrivePrepareDeleteFileInput,
    DrivePrepareRevokePermissionInput,
    DrivePrepareSaveFileInput,
    DrivePrepareShareFileInput,
    DrivePrepareUploadInput,
    DrivePrepareWriteGoogleDocInput,
    DrivePrepareWriteGoogleSheetInput,
    DriveSearchFilesAdvancedInput,
    DriveSearchFilesInput,
    DriveUpdateMetadataInput,
    is_google_native_mime_type,
)
from app.services.connection_service import ConnectionService
from app.services.pending_operations import (
    _as_str,
    _get_pending_operation_record,
    _preview_from_record,
    confirmed_operation,
    create_pending_operation,
)
from app.services.response_enrichment import enrich_collection, enrich_resource

EXPORT_MIME_TYPES: dict[str, set[str]] = {
    "application/vnd.google-apps.document": {
        "text/plain",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    "application/vnd.google-apps.spreadsheet": {
        "text/csv",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
    "application/vnd.google-apps.presentation": {
        "text/plain",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    },
}

GOOGLE_NATIVE_CREATE_TYPES: dict[str, str] = {
    "document": "application/vnd.google-apps.document",
    "spreadsheet": "application/vnd.google-apps.spreadsheet",
    "presentation": "application/vnd.google-apps.presentation",
}

FILE_TYPE_TO_MIME_TYPES: dict[str, list[str] | None] = {
    "any": None,
    "folder": ["application/vnd.google-apps.folder"],
    "doc": ["application/vnd.google-apps.document"],
    "sheet": ["application/vnd.google-apps.spreadsheet"],
    "pdf": ["application/pdf"],
}

MIME_TYPE_TO_FILE_TYPE: dict[str, str] = {
    "application/vnd.google-apps.folder": "folder",
    "application/vnd.google-apps.document": "doc",
    "application/vnd.google-apps.spreadsheet": "sheet",
    "application/pdf": "pdf",
}


class DriveService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.client = DriveClient(session, self.settings)
        self.connections = ConnectionService(session)
        self.pending_operations = PendingGoogleOperationRepository(session)

    def list_files(
        self,
        *,
        external_subject: str,
        input_data: DriveListFilesInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        payload = self.client.list_files(
            external_subject=external_subject,
            tenant_id=tenant_id,
            query=_build_drive_query(
                parent_id=input_data.parent_id, include_trashed=input_data.include_trashed
            ),
            page_size=input_data.page_size,
            page_token=input_data.page_token,
        )
        normalized = _normalize_file_list(payload)
        raw_items = normalized.get("items")
        items = cast(list[dict[str, object]], raw_items) if isinstance(raw_items, list) else []
        next_page_token_raw = normalized.get("next_page_token")
        next_page_token = cast(
            str | None, next_page_token_raw if isinstance(next_page_token_raw, str) else None
        )
        return enrich_collection(
            items=items,
            next_page_token=next_page_token,
            resource_type="drive_file_collection",
            parent_id=input_data.parent_id,
            human_summary=f"Found {len(items)} Drive file(s).",
            next_suggested_actions=["drive_search_files", "drive_get_file", "drive_create_folder"],
            safety_level="read",
        )

    def search_files(
        self,
        *,
        external_subject: str,
        input_data: DriveSearchFilesInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        query = _build_drive_query(
            text_query=input_data.query,
            name=input_data.name,
            mime_type=input_data.mime_type,
            parent_id=input_data.parent_id,
            include_trashed=input_data.include_trashed,
        )
        payload = self.client.list_files(
            external_subject=external_subject,
            tenant_id=tenant_id,
            query=query,
            page_size=input_data.page_size,
            page_token=input_data.page_token,
        )
        normalized = _normalize_file_list(payload)
        raw_items = normalized.get("items")
        items = cast(list[dict[str, object]], raw_items) if isinstance(raw_items, list) else []
        next_page_token_raw = normalized.get("next_page_token")
        next_page_token = cast(
            str | None, next_page_token_raw if isinstance(next_page_token_raw, str) else None
        )
        return enrich_collection(
            items=items,
            next_page_token=next_page_token,
            resource_type="drive_file_collection",
            parent_id=input_data.parent_id,
            human_summary=f"Found {len(items)} matching Drive file(s).",
            next_suggested_actions=[
                "drive_get_file",
                "drive_download_file",
                "drive_prepare_share_file",
            ],
            safety_level="read",
        )

    def find_folder_by_name(
        self,
        *,
        external_subject: str,
        input_data: DriveFindFolderByNameInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        return self._smart_find_by_name(
            external_subject=external_subject,
            tenant_id=tenant_id,
            name=input_data.name,
            file_type="folder",
            exact=input_data.exact,
            normalized=input_data.normalized,
            include_trashed=input_data.include_trashed,
            parent_id=input_data.parent_id,
            max_results=input_data.max_results,
        )

    def find_file_by_name(
        self,
        *,
        external_subject: str,
        input_data: DriveFindFileByNameInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        return self._smart_find_by_name(
            external_subject=external_subject,
            tenant_id=tenant_id,
            name=input_data.name,
            file_type=input_data.file_type,
            exact=input_data.exact,
            normalized=input_data.normalized,
            include_trashed=input_data.include_trashed,
            parent_id=input_data.parent_id,
            max_results=input_data.max_results,
        )

    def search_files_advanced(
        self,
        *,
        external_subject: str,
        input_data: DriveSearchFilesAdvancedInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        terms = [term.strip() for term in input_data.terms if term.strip()]
        seen_ids: set[str] = set()
        queries: set[str | None] = set()
        candidates: list[dict[str, object]] = []
        strategies: list[str] = []

        phrase = " ".join(terms)
        if phrase:
            candidates.extend(
                self._collect_drive_candidates(
                    external_subject=external_subject,
                    tenant_id=tenant_id,
                    name=phrase,
                    mime_types=input_data.mime_types,
                    include_trashed=input_data.include_trashed,
                    parent_id=input_data.parent_id,
                    page_size=input_data.page_size,
                    seen_ids=seen_ids,
                    queries=queries,
                    strategy_name="phrase_partial",
                    strategies=strategies,
                )
            )
        token_name = " ".join(terms) if input_data.match_mode == "all_terms" else None
        for term in terms:
            candidates.extend(
                self._collect_drive_candidates(
                    external_subject=external_subject,
                    tenant_id=tenant_id,
                    name=token_name or term,
                    mime_types=input_data.mime_types,
                    include_trashed=input_data.include_trashed,
                    parent_id=input_data.parent_id,
                    page_size=input_data.page_size,
                    seen_ids=seen_ids,
                    queries=queries,
                    strategy_name=f"term:{term}",
                    strategies=strategies,
                )
            )

        matches = self._rank_candidates(
            candidates=candidates,
            target_name=phrase,
            normalized=input_data.normalized,
            allow_fuzzy=input_data.fuzzy,
            required_terms=terms if input_data.match_mode == "all_terms" else [],
            preferred_terms=terms,
            max_results=input_data.page_size,
        )
        return self._build_smart_search_response(
            matches=matches,
            query_used={
                "terms": terms,
                "mime_types": input_data.mime_types or [],
                "match_mode": input_data.match_mode,
                "normalized": input_data.normalized,
                "fuzzy": input_data.fuzzy,
                "include_trashed": input_data.include_trashed,
                "parent_id": input_data.parent_id,
                "strategies": strategies,
                "incomplete": "budget_exhausted" in strategies,
            },
            resource_type="drive_file_collection",
            human_summary=_build_find_summary(matches, label="Drive file"),
            next_suggested_actions=[
                "drive_get_file",
                "drive_export_file",
                "drive_prepare_share_file",
            ],
        )

    def get_file(
        self,
        *,
        external_subject: str,
        input_data: DriveGetFileInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        payload = self.client.get_file(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=input_data.file_id,
        )
        normalized = _normalize_file(payload)
        return enrich_resource(
            normalized,
            resource_type="drive_file",
            file_id=normalized.get("id"),
            human_summary=f"Loaded Drive file '{normalized.get('name') or normalized.get('id')}'.",
            next_suggested_actions=[
                "drive_download_file",
                "drive_update_metadata",
                "drive_prepare_share_file",
            ],
            safety_level="read",
        )

    def list_permissions(
        self,
        *,
        external_subject: str,
        input_data: DriveListPermissionsInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        payload = self.client.list_permissions(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=input_data.file_id,
        )
        permission_items_raw = payload.get("permissions")
        permission_items: list[dict[str, object]] = []
        if isinstance(permission_items_raw, list):
            permission_items = [item for item in permission_items_raw if isinstance(item, dict)]
        items: list[dict[str, object]] = [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "role": item.get("role"),
                "email_address": item.get("emailAddress"),
                "domain": item.get("domain"),
                "allow_file_discovery": item.get("allowFileDiscovery"),
                "display_name": item.get("displayName"),
            }
            for item in permission_items
        ]
        return enrich_collection(
            items=items,
            resource_type="drive_permission_collection",
            file_id=input_data.file_id,
            human_summary=f"Found {len(items)} permission(s) for Drive file '{input_data.file_id}'.",
            next_suggested_actions=[
                "drive_prepare_share_file",
                "drive_prepare_revoke_permission",
                "drive_get_file",
            ],
            safety_level="read",
        )

    def download_file(
        self,
        *,
        external_subject: str,
        input_data: DriveDownloadFileInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        metadata = self.get_file(
            external_subject=external_subject,
            input_data=DriveGetFileInput(file_id=input_data.file_id),
            tenant_id=tenant_id,
        )
        if is_google_native_mime_type(_as_str(metadata.get("mime_type"))):
            raise DriveNativeEditNotSupportedError(
                "Use drive_export_file for native Google Workspace files"
            )
        declared_size = metadata.get("size")
        if declared_size is not None:
            try:
                _ensure_size_limit(
                    int(declared_size), self.settings.drive_inline_content_limit_bytes
                )
            except (ValueError, TypeError):
                raise ValidationError("Invalid Drive file size") from None
        content = self.client.download_file(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=input_data.file_id,
        )
        _ensure_size_limit(len(content), self.settings.drive_inline_content_limit_bytes)
        result = {
            "file": metadata,
            "content_base64": encode_bytes_to_base64(content),
            "content_size": len(content),
        }
        return enrich_resource(
            result,
            resource_type="drive_file_content",
            file_id=metadata.get("id"),
            human_summary=f"Downloaded Drive file '{metadata.get('name') or metadata.get('id')}'.",
            next_suggested_actions=["drive_get_file", "drive_prepare_save_file"],
            safety_level="read",
        )

    def export_file(
        self,
        *,
        external_subject: str,
        input_data: DriveExportFileInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        metadata = self.get_file(
            external_subject=external_subject,
            input_data=DriveGetFileInput(file_id=input_data.file_id),
            tenant_id=tenant_id,
        )
        mime_type = _as_str(metadata.get("mime_type"))
        allowed = EXPORT_MIME_TYPES.get(mime_type, set())
        if input_data.export_mime_type not in allowed:
            raise DriveExportNotSupportedError(
                f"Export '{input_data.export_mime_type}' is not supported for '{mime_type}'"
            )
        content = self.client.export_file(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=input_data.file_id,
            export_mime_type=input_data.export_mime_type,
        )
        _ensure_size_limit(len(content), self.settings.drive_inline_content_limit_bytes)
        result = {
            "file": metadata,
            "export_mime_type": input_data.export_mime_type,
            "content_base64": encode_bytes_to_base64(content),
            "content_size": len(content),
        }
        return enrich_resource(
            result,
            resource_type="drive_file_export",
            file_id=metadata.get("id"),
            human_summary=f"Exported Drive file '{metadata.get('name') or metadata.get('id')}' as {input_data.export_mime_type}.",
            next_suggested_actions=["drive_get_file", "drive_download_file"],
            safety_level="read",
        )

    def create_folder(
        self,
        *,
        external_subject: str,
        input_data: DriveCreateFolderInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        payload = self.client.create_folder(
            external_subject=external_subject,
            tenant_id=tenant_id,
            name=input_data.name,
            parent_id=input_data.parent_id,
        )
        normalized = _normalize_file(payload)
        return enrich_resource(
            normalized,
            resource_type="drive_folder",
            file_id=normalized.get("id"),
            human_summary=f"Created Drive folder '{normalized.get('name') or normalized.get('id')}'.",
            next_suggested_actions=[
                "drive_list_files",
                "drive_create_shortcut",
                "drive_update_metadata",
            ],
            safety_level="write",
        )

    def create_google_doc(
        self,
        *,
        external_subject: str,
        input_data: DriveCreateNativeFileInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        return self._create_native_file(
            external_subject=external_subject,
            input_data=input_data,
            tenant_id=tenant_id,
            native_kind="document",
            summary_label="Google Doc",
            next_suggested_actions=[
                "drive_get_file",
                "drive_export_file",
                "drive_prepare_share_file",
            ],
        )

    def create_google_sheet(
        self,
        *,
        external_subject: str,
        input_data: DriveCreateNativeFileInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        return self._create_native_file(
            external_subject=external_subject,
            input_data=input_data,
            tenant_id=tenant_id,
            native_kind="spreadsheet",
            summary_label="Google Sheet",
            next_suggested_actions=[
                "drive_get_file",
                "drive_export_file",
                "drive_prepare_share_file",
            ],
        )

    def create_google_slide(
        self,
        *,
        external_subject: str,
        input_data: DriveCreateNativeFileInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        return self._create_native_file(
            external_subject=external_subject,
            input_data=input_data,
            tenant_id=tenant_id,
            native_kind="presentation",
            summary_label="Google Slide deck",
            next_suggested_actions=[
                "drive_get_file",
                "drive_export_file",
                "drive_prepare_share_file",
            ],
        )

    def prepare_write_google_doc(
        self,
        *,
        external_subject: str,
        input_data: DrivePrepareWriteGoogleDocInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        metadata = self.get_file(
            external_subject=external_subject,
            input_data=DriveGetFileInput(file_id=input_data.file_id),
            tenant_id=tenant_id,
        )
        mime_type = _as_str(metadata.get("mime_type"))
        if mime_type != GOOGLE_NATIVE_CREATE_TYPES["document"]:
            raise DriveNativeEditNotSupportedError(
                "This tool only supports native Google Docs documents"
            )
        size = len(input_data.content_text.encode("utf-8"))
        _ensure_size_limit(size, self.settings.drive_inline_content_limit_bytes)
        record = self._create_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type="drive_write_google_doc",
            resource_type="drive_file",
            resource_id=input_data.file_id,
            resource_name=_nullable_str(metadata.get("name")),
            payload_normalized=input_data.model_dump(exclude_none=True),
        )
        return _preview_from_record(
            record,
            risk_level="high",
            summary={
                "action": "write_google_doc",
                "file_id": input_data.file_id,
                "name": metadata.get("name"),
                "mode": input_data.mode,
                "content_size": size,
            },
        )

    @confirmed_operation
    def confirm_write_google_doc(
        self,
        *,
        external_subject: str,
        input_data: DriveConfirmOperationInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        record = self._get_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=input_data.operation_id,
            expected_operation_type="drive_write_google_doc",
        )
        payload = record.payload_normalized
        file_id = _as_str(payload.get("file_id"))
        content_text = _as_str(payload.get("content_text"))
        mode = _as_str(payload.get("mode"))
        self.client.write_google_doc(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=file_id,
            content_text=content_text,
            mode=mode,
        )
        self.pending_operations.mark_confirmed(record)
        self.session.commit()
        metadata = self.get_file(
            external_subject=external_subject,
            input_data=DriveGetFileInput(file_id=file_id),
            tenant_id=tenant_id,
        )
        result = {
            "operation_id": input_data.operation_id,
            "confirmed": True,
            "file": metadata,
            "mode": mode,
        }
        return enrich_resource(
            result,
            resource_type="drive_file",
            file_id=file_id,
            human_summary=f"Wrote content to Google Doc '{record.resource_name or file_id}'.",
            next_suggested_actions=[
                "drive_get_file",
                "drive_export_file",
                "drive_prepare_share_file",
            ],
            safety_level="destructive",
        )

    def prepare_write_google_sheet(
        self,
        *,
        external_subject: str,
        input_data: DrivePrepareWriteGoogleSheetInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        metadata = self.get_file(
            external_subject=external_subject,
            input_data=DriveGetFileInput(file_id=input_data.file_id),
            tenant_id=tenant_id,
        )
        mime_type = _as_str(metadata.get("mime_type"))
        if mime_type != GOOGLE_NATIVE_CREATE_TYPES["spreadsheet"]:
            raise DriveNativeEditNotSupportedError(
                "This tool only supports native Google Sheets spreadsheets"
            )
        serialized_values = str(input_data.values)
        size = len(serialized_values.encode("utf-8"))
        _ensure_size_limit(size, self.settings.drive_inline_content_limit_bytes)
        record = self._create_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type="drive_write_google_sheet",
            resource_type="drive_file",
            resource_id=input_data.file_id,
            resource_name=_nullable_str(metadata.get("name")),
            payload_normalized=input_data.model_dump(exclude_none=True),
        )
        row_count = len(input_data.values)
        col_count = max((len(row) for row in input_data.values), default=0)
        return _preview_from_record(
            record,
            risk_level="high",
            summary={
                "action": "write_google_sheet",
                "file_id": input_data.file_id,
                "name": metadata.get("name"),
                "mode": input_data.mode,
                "sheet_name": input_data.sheet_name,
                "create_sheet_if_missing": input_data.create_sheet_if_missing,
                "start_cell": input_data.start_cell,
                "rows": row_count,
                "columns": col_count,
            },
        )

    @confirmed_operation
    def confirm_write_google_sheet(
        self,
        *,
        external_subject: str,
        input_data: DriveConfirmOperationInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        record = self._get_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=input_data.operation_id,
            expected_operation_type="drive_write_google_sheet",
        )
        payload = record.payload_normalized
        file_id = _as_str(payload.get("file_id"))
        values = payload.get("values")
        if not isinstance(values, list):
            raise ValidationError("Pending sheet values payload is invalid")
        normalized_values: list[list[str | int | float | bool | None]] = []
        for row in values:
            if not isinstance(row, list):
                raise ValidationError("Pending sheet row payload is invalid")
            normalized_values.append(
                [
                    cell if isinstance(cell, (str, int, float, bool)) or cell is None else str(cell)
                    for cell in row
                ]
            )
        mode = _as_str(payload.get("mode"))
        start_cell = _as_str(payload.get("start_cell"))
        sheet_name = _nullable_str(payload.get("sheet_name"))
        create_sheet_if_missing = bool(payload.get("create_sheet_if_missing", False))
        self.client.write_google_sheet(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=file_id,
            values=normalized_values,
            sheet_name=sheet_name,
            create_sheet_if_missing=create_sheet_if_missing,
            start_cell=start_cell,
            mode=mode,
        )
        self.pending_operations.mark_confirmed(record)
        self.session.commit()
        metadata = self.get_file(
            external_subject=external_subject,
            input_data=DriveGetFileInput(file_id=file_id),
            tenant_id=tenant_id,
        )
        result = {
            "operation_id": input_data.operation_id,
            "confirmed": True,
            "file": metadata,
            "mode": mode,
            "sheet_name": sheet_name,
            "create_sheet_if_missing": create_sheet_if_missing,
            "start_cell": start_cell,
        }
        return enrich_resource(
            result,
            resource_type="drive_file",
            file_id=file_id,
            human_summary=f"Wrote values to Google Sheet '{record.resource_name or file_id}'.",
            next_suggested_actions=[
                "drive_get_file",
                "drive_export_file",
                "drive_prepare_share_file",
            ],
            safety_level="destructive",
        )

    def create_shortcut(
        self,
        *,
        external_subject: str,
        input_data: DriveCreateShortcutInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        payload = self.client.create_shortcut(
            external_subject=external_subject,
            tenant_id=tenant_id,
            name=input_data.name,
            target_file_id=input_data.target_file_id,
            parent_id=input_data.parent_id,
        )
        normalized = _normalize_file(payload)
        return enrich_resource(
            normalized,
            resource_type="drive_shortcut",
            file_id=normalized.get("id"),
            human_summary=f"Created Drive shortcut '{normalized.get('name') or normalized.get('id')}'.",
            next_suggested_actions=[
                "drive_get_file",
                "drive_move_file",
                "drive_prepare_delete_file",
            ],
            safety_level="write",
        )

    def _create_native_file(
        self,
        *,
        external_subject: str,
        input_data: DriveCreateNativeFileInput,
        tenant_id: str | None,
        native_kind: str,
        summary_label: str,
        next_suggested_actions: list[str],
    ) -> dict[str, object]:
        mime_type = GOOGLE_NATIVE_CREATE_TYPES[native_kind]
        payload = self.client.create_native_file(
            external_subject=external_subject,
            tenant_id=tenant_id,
            name=input_data.name,
            mime_type=mime_type,
            parent_id=input_data.parent_id,
        )
        normalized = _normalize_file(payload)
        return enrich_resource(
            normalized,
            resource_type="drive_file",
            file_id=normalized.get("id"),
            human_summary=f"Created {summary_label} '{normalized.get('name') or normalized.get('id')}'.",
            next_suggested_actions=next_suggested_actions,
            safety_level="write",
        )

    def _smart_find_by_name(
        self,
        *,
        external_subject: str,
        tenant_id: str | None,
        name: str,
        file_type: str,
        exact: bool,
        normalized: bool,
        include_trashed: bool,
        parent_id: str | None,
        max_results: int,
    ) -> dict[str, object]:
        mime_types = FILE_TYPE_TO_MIME_TYPES[file_type]
        seen_ids: set[str] = set()
        queries: set[str | None] = set()
        candidates: list[dict[str, object]] = []
        strategies: list[str] = []
        normalized_name = _normalize_match_text(name)

        if exact:
            candidates.extend(
                self._collect_drive_candidates(
                    external_subject=external_subject,
                    tenant_id=tenant_id,
                    exact_name=name,
                    mime_types=mime_types,
                    include_trashed=include_trashed,
                    parent_id=parent_id,
                    page_size=max_results,
                    seen_ids=seen_ids,
                    queries=queries,
                    strategy_name="exact_original",
                    strategies=strategies,
                )
            )
        if not candidates and normalized and normalized_name and normalized_name != name.casefold():
            candidates.extend(
                self._collect_drive_candidates(
                    external_subject=external_subject,
                    tenant_id=tenant_id,
                    name=normalized_name,
                    mime_types=mime_types,
                    include_trashed=include_trashed,
                    parent_id=parent_id,
                    page_size=max_results,
                    seen_ids=seen_ids,
                    queries=queries,
                    strategy_name="exact_normalized_candidate",
                    strategies=strategies,
                )
            )
        if not candidates:
            candidates.extend(
                self._collect_drive_candidates(
                    external_subject=external_subject,
                    tenant_id=tenant_id,
                    name=name,
                    mime_types=mime_types,
                    include_trashed=include_trashed,
                    parent_id=parent_id,
                    page_size=max_results,
                    seen_ids=seen_ids,
                    queries=queries,
                    strategy_name="partial_original",
                    strategies=strategies,
                )
            )
        if not candidates:
            for token in _tokenize_match_text(name):
                candidates.extend(
                    self._collect_drive_candidates(
                        external_subject=external_subject,
                        tenant_id=tenant_id,
                        name=token,
                        mime_types=mime_types,
                        include_trashed=include_trashed,
                        parent_id=parent_id,
                        page_size=max_results,
                        seen_ids=seen_ids,
                        queries=queries,
                        strategy_name=f"token:{token}",
                        strategies=strategies,
                    )
                )
                if candidates:
                    break

        matches = self._rank_candidates(
            candidates=candidates,
            target_name=name,
            normalized=normalized,
            allow_fuzzy=True,
            required_terms=[],
            preferred_terms=_tokenize_match_text(name),
            max_results=max_results,
        )
        return self._build_smart_search_response(
            matches=matches,
            query_used={
                "name": name,
                "file_type": file_type,
                "exact": exact,
                "normalized": normalized,
                "include_trashed": include_trashed,
                "parent_id": parent_id,
                "strategies": strategies,
                "incomplete": "budget_exhausted" in strategies,
            },
            resource_type="drive_file_collection",
            human_summary=_build_find_summary(
                matches, label="Drive file" if file_type != "folder" else "Drive folder"
            ),
            next_suggested_actions=[
                "drive_get_file",
                "drive_export_file",
                "drive_prepare_share_file",
            ],
        )

    def _collect_drive_candidates(
        self,
        *,
        external_subject: str,
        tenant_id: str | None,
        seen_ids: set[str],
        queries: set[str | None],
        strategy_name: str,
        strategies: list[str],
        page_size: int,
        exact_name: str | None = None,
        name: str | None = None,
        mime_types: list[str] | None = None,
        include_trashed: bool,
        parent_id: str | None,
    ) -> list[dict[str, object]]:
        strategies.append(strategy_name)
        raw_items: list[dict[str, object]] = []
        target_mime_types = mime_types or [None]
        for mime_type in target_mime_types:
            query = _build_drive_query(
                exact_name=exact_name,
                name=name,
                mime_type=mime_type,
                parent_id=parent_id,
                include_trashed=include_trashed,
            )
            if query in queries:
                continue
            if len(queries) >= 16:
                if "budget_exhausted" not in strategies:
                    strategies.append("budget_exhausted")
                break
            queries.add(query)
            payload = self.client.list_files(
                external_subject=external_subject,
                tenant_id=tenant_id,
                query=query,
                page_size=page_size,
            )
            normalized = _normalize_file_list(payload)
            items = normalized.get("items")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                file_id = _nullable_str(item.get("id"))
                if not file_id or file_id in seen_ids:
                    continue
                seen_ids.add(file_id)
                raw_items.append(item)
        return raw_items

    def _rank_candidates(
        self,
        *,
        candidates: list[dict[str, object]],
        target_name: str,
        normalized: bool,
        allow_fuzzy: bool,
        required_terms: list[str],
        preferred_terms: list[str],
        max_results: int,
    ) -> list[dict[str, object]]:
        ranked: list[dict[str, object]] = []
        for item in candidates:
            match = _score_drive_match(
                item=item,
                target_name=target_name,
                normalized=normalized,
                allow_fuzzy=allow_fuzzy,
                required_terms=required_terms,
                preferred_terms=preferred_terms,
            )
            if match is not None:
                ranked.append(match)
        ranked.sort(
            key=lambda item: (
                -float(item.get("score", 0.0)),
                _sortable_modified_time(item.get("modified_time")),
            )
        )
        return ranked[:max_results]

    def _build_smart_search_response(
        self,
        *,
        matches: list[dict[str, object]],
        query_used: dict[str, object],
        resource_type: str,
        human_summary: str,
        next_suggested_actions: list[str],
    ) -> dict[str, object]:
        best_match = matches[0] if matches else None
        status = _resolve_match_status(matches)
        payload: dict[str, object] = {
            "status": status,
            "best_match": best_match,
            "matches": matches,
            "matches_count": len(matches),
            "query_used": query_used,
        }
        return enrich_resource(
            payload,
            resource_type=resource_type,
            human_summary=human_summary,
            next_suggested_actions=next_suggested_actions,
            safety_level="read",
            status=status,
        )

    def update_metadata(
        self,
        *,
        external_subject: str,
        input_data: DriveUpdateMetadataInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        body = input_data.model_dump(exclude_none=True)
        body.pop("file_id", None)
        payload = self.client.update_metadata(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=input_data.file_id,
            metadata_body=body,
        )
        normalized = _normalize_file(payload)
        return enrich_resource(
            normalized,
            resource_type="drive_file",
            file_id=normalized.get("id"),
            human_summary=f"Updated metadata for Drive file '{normalized.get('name') or normalized.get('id')}'.",
            next_suggested_actions=[
                "drive_get_file",
                "drive_move_file",
                "drive_prepare_share_file",
            ],
            safety_level="write",
        )

    def move_file(
        self,
        *,
        external_subject: str,
        input_data: DriveMoveFileInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        payload = self.client.move_file(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=input_data.file_id,
            add_parent_id=input_data.add_parent_id,
            remove_parent_id=input_data.remove_parent_id,
        )
        normalized = _normalize_file(payload)
        return enrich_resource(
            normalized,
            resource_type="drive_file",
            file_id=normalized.get("id"),
            human_summary=f"Moved Drive file '{normalized.get('name') or normalized.get('id')}'.",
            next_suggested_actions=[
                "drive_get_file",
                "drive_list_files",
                "drive_prepare_share_file",
            ],
            safety_level="write",
        )

    def prepare_upload(
        self,
        *,
        external_subject: str,
        input_data: DrivePrepareUploadInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        content_bytes, _ = _decode_content_payload(
            input_data.content.model_dump(), self.settings.drive_inline_content_limit_bytes
        )
        size = len(content_bytes)
        _ensure_size_limit(size, self.settings.drive_inline_content_limit_bytes)
        record = self._create_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type="drive_upload",
            resource_type="drive_file",
            resource_name=input_data.name,
            payload_normalized=input_data.model_dump(exclude_none=True),
        )
        return _preview_from_record(
            record,
            risk_level="high",
            summary={
                "action": "upload_file",
                "name": input_data.name,
                "parent_id": input_data.parent_id,
                "mime_type": input_data.content.mime_type,
                "content_size": size,
            },
        )

    @confirmed_operation
    def confirm_upload(
        self,
        *,
        external_subject: str,
        input_data: DriveConfirmOperationInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        record = self._get_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=input_data.operation_id,
            expected_operation_type="drive_upload",
        )
        payload = record.payload_normalized
        content_bytes, mime_type = _decode_content_payload(
            payload.get("content", {}), self.settings.drive_inline_content_limit_bytes
        )
        result = self.client.upload_file(
            external_subject=external_subject,
            tenant_id=tenant_id,
            name=_as_str(payload.get("name")),
            parent_id=_nullable_str(payload.get("parent_id")),
            mime_type=mime_type,
            content_bytes=content_bytes,
        )
        self.pending_operations.mark_confirmed(record)
        self.session.commit()
        result = {
            "operation_id": input_data.operation_id,
            "confirmed": True,
            "file": _normalize_file(result),
        }
        file_payload = result["file"] if isinstance(result.get("file"), dict) else {}
        return enrich_resource(
            result,
            resource_type="drive_file",
            file_id=file_payload.get("id") if isinstance(file_payload, dict) else None,
            human_summary=f"Uploaded Drive file '{record.resource_name or 'file'}'.",
            next_suggested_actions=[
                "drive_get_file",
                "drive_prepare_share_file",
                "drive_prepare_delete_file",
            ],
            safety_level="destructive",
        )

    def prepare_save_file(
        self,
        *,
        external_subject: str,
        input_data: DrivePrepareSaveFileInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        metadata = self.get_file(
            external_subject=external_subject,
            input_data=DriveGetFileInput(file_id=input_data.file_id),
            tenant_id=tenant_id,
        )
        mime_type = _as_str(metadata.get("mime_type"))
        if is_google_native_mime_type(mime_type):
            raise DriveNativeEditNotSupportedError()
        content_bytes, _ = _decode_content_payload(
            input_data.content.model_dump(), self.settings.drive_inline_content_limit_bytes
        )
        size = len(content_bytes)
        _ensure_size_limit(size, self.settings.drive_inline_content_limit_bytes)
        record = self._create_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type="drive_save",
            resource_type="drive_file",
            resource_id=input_data.file_id,
            resource_name=_nullable_str(metadata.get("name")),
            payload_normalized=input_data.model_dump(exclude_none=True),
        )
        return _preview_from_record(
            record,
            risk_level="high",
            summary={
                "action": "save_file_content",
                "file_id": input_data.file_id,
                "name": metadata.get("name"),
                "mime_type": input_data.content.mime_type,
                "content_size": size,
            },
        )

    @confirmed_operation
    def confirm_save_file(
        self,
        *,
        external_subject: str,
        input_data: DriveConfirmOperationInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        record = self._get_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=input_data.operation_id,
            expected_operation_type="drive_save",
        )
        payload = record.payload_normalized
        file_id = _as_str(payload.get("file_id"))
        metadata = self.get_file(
            external_subject=external_subject,
            input_data=DriveGetFileInput(file_id=file_id),
            tenant_id=tenant_id,
        )
        if is_google_native_mime_type(_as_str(metadata.get("mime_type"))):
            raise DriveNativeEditNotSupportedError()
        content_bytes, mime_type = _decode_content_payload(
            payload.get("content", {}), self.settings.drive_inline_content_limit_bytes
        )
        result = self.client.update_file_content(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=file_id,
            mime_type=mime_type,
            content_bytes=content_bytes,
        )
        self.pending_operations.mark_confirmed(record)
        self.session.commit()
        result = {
            "operation_id": input_data.operation_id,
            "confirmed": True,
            "file": _normalize_file(result),
        }
        file_payload = result["file"] if isinstance(result.get("file"), dict) else {}
        return enrich_resource(
            result,
            resource_type="drive_file",
            file_id=file_payload.get("id") if isinstance(file_payload, dict) else None,
            human_summary=f"Saved content to Drive file '{record.resource_name or file_id}'.",
            next_suggested_actions=[
                "drive_get_file",
                "drive_download_file",
                "drive_prepare_delete_file",
            ],
            safety_level="destructive",
        )

    def prepare_delete_file(
        self,
        *,
        external_subject: str,
        input_data: DrivePrepareDeleteFileInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        metadata = self.get_file(
            external_subject=external_subject,
            input_data=DriveGetFileInput(file_id=input_data.file_id),
            tenant_id=tenant_id,
        )
        record = self._create_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type="drive_delete",
            resource_type="drive_file",
            resource_id=input_data.file_id,
            resource_name=_nullable_str(metadata.get("name")),
            payload_normalized=input_data.model_dump(exclude_none=True),
        )
        return _preview_from_record(
            record,
            risk_level="critical" if input_data.permanent else "high",
            summary={
                "action": "delete_file_permanently" if input_data.permanent else "trash_file",
                "file_id": input_data.file_id,
                "name": metadata.get("name"),
                "mime_type": metadata.get("mime_type"),
            },
        )

    @confirmed_operation
    def confirm_delete_file(
        self,
        *,
        external_subject: str,
        input_data: DriveConfirmOperationInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        record = self._get_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=input_data.operation_id,
            expected_operation_type="drive_delete",
        )
        payload = record.payload_normalized
        file_id = _as_str(payload.get("file_id"))
        permanent = bool(payload.get("permanent", False))
        if permanent:
            self.client.delete_file_permanently(
                external_subject=external_subject,
                tenant_id=tenant_id,
                file_id=file_id,
            )
            result: dict[str, object] = {
                "deleted": True,
                "permanent": True,
                "file_id": file_id,
            }
        else:
            payload_result = self.client.trash_file(
                external_subject=external_subject,
                tenant_id=tenant_id,
                file_id=file_id,
            )
            result = {"deleted": True, "permanent": False, "file": _normalize_file(payload_result)}
        self.pending_operations.mark_confirmed(record)
        self.session.commit()
        response = {"operation_id": input_data.operation_id, "confirmed": True, **result}
        return enrich_resource(
            response,
            resource_type="drive_file",
            file_id=file_id,
            human_summary=f"Deleted Drive file '{record.resource_name or file_id}'.",
            next_suggested_actions=["drive_list_files", "drive_create_folder"],
            safety_level="destructive",
        )

    def prepare_share_file(
        self,
        *,
        external_subject: str,
        input_data: DrivePrepareShareFileInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        metadata = self.get_file(
            external_subject=external_subject,
            input_data=DriveGetFileInput(file_id=input_data.file_id),
            tenant_id=tenant_id,
        )
        record = self._create_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type="drive_share",
            resource_type="drive_permission",
            resource_id=input_data.file_id,
            resource_name=_nullable_str(metadata.get("name")),
            payload_normalized=input_data.model_dump(exclude_none=True),
        )
        return _preview_from_record(
            record,
            risk_level="high",
            summary={
                "action": "share_file",
                "file_id": input_data.file_id,
                "name": metadata.get("name"),
                "permission": input_data.permission.model_dump(exclude_none=True),
            },
        )

    @confirmed_operation
    def confirm_share_file(
        self,
        *,
        external_subject: str,
        input_data: DriveConfirmOperationInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        record = self._get_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=input_data.operation_id,
            expected_operation_type="drive_share",
        )
        payload = record.payload_normalized
        file_id = _as_str(payload.get("file_id"))
        permission_payload = payload.get("permission")
        if not isinstance(permission_payload, dict):
            raise ValidationError("Drive permission payload is invalid")
        result = self.client.create_permission(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=file_id,
            permission_body=permission_payload,
        )
        self.pending_operations.mark_confirmed(record)
        self.session.commit()
        result = {
            "operation_id": input_data.operation_id,
            "confirmed": True,
            "file_id": file_id,
            "permission": _normalize_permission(result),
        }
        return enrich_resource(
            result,
            resource_type="drive_permission",
            file_id=file_id,
            human_summary=f"Shared Drive file '{record.resource_name or file_id}'.",
            next_suggested_actions=[
                "drive_list_permissions",
                "drive_prepare_revoke_permission",
                "drive_get_file",
            ],
            safety_level="destructive",
        )

    def prepare_revoke_permission(
        self,
        *,
        external_subject: str,
        input_data: DrivePrepareRevokePermissionInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        metadata = self.get_file(
            external_subject=external_subject,
            input_data=DriveGetFileInput(file_id=input_data.file_id),
            tenant_id=tenant_id,
        )
        record = self._create_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type="drive_revoke_permission",
            resource_type="drive_permission",
            resource_id=input_data.file_id,
            resource_name=_nullable_str(metadata.get("name")),
            payload_normalized=input_data.model_dump(exclude_none=True),
        )
        return _preview_from_record(
            record,
            risk_level="high",
            summary={
                "action": "revoke_permission",
                "file_id": input_data.file_id,
                "name": metadata.get("name"),
                "permission_id": input_data.permission_id,
            },
        )

    @confirmed_operation
    def confirm_revoke_permission(
        self,
        *,
        external_subject: str,
        input_data: DriveConfirmOperationInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        record = self._get_pending_operation(
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=input_data.operation_id,
            expected_operation_type="drive_revoke_permission",
        )
        payload = record.payload_normalized
        file_id = _as_str(payload.get("file_id"))
        permission_id = _as_str(payload.get("permission_id"))
        self.client.delete_permission(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=file_id,
            permission_id=permission_id,
        )
        self.pending_operations.mark_confirmed(record)
        self.session.commit()
        result = {
            "operation_id": input_data.operation_id,
            "confirmed": True,
            "file_id": file_id,
            "permission_id": permission_id,
            "revoked": True,
        }
        return enrich_resource(
            result,
            resource_type="drive_permission",
            file_id=file_id,
            permission_id=permission_id,
            human_summary=f"Revoked Drive permission '{permission_id}' from '{record.resource_name or file_id}'.",
            next_suggested_actions=[
                "drive_list_permissions",
                "drive_prepare_share_file",
                "drive_get_file",
            ],
            safety_level="destructive",
        )

    def _create_pending_operation(
        self,
        *,
        external_subject: str,
        tenant_id: str | None,
        operation_type: str,
        resource_type: str,
        payload_normalized: dict[str, object],
        resource_id: str | None = None,
        resource_name: str | None = None,
    ) -> PendingGoogleOperation:
        return create_pending_operation(
            self,
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_type=operation_type,
            resource_type=resource_type,
            payload_normalized=payload_normalized,
            resource_id=resource_id,
            resource_name=resource_name,
        )

    def _get_pending_operation(
        self,
        *,
        external_subject: str,
        tenant_id: str | None,
        operation_id: str,
        expected_operation_type: str,
    ) -> PendingGoogleOperation:
        return _get_pending_operation_record(
            session=self.session,
            connections=self.connections,
            pending_operations=self.pending_operations,
            external_subject=external_subject,
            tenant_id=tenant_id,
            operation_id=operation_id,
            expected_operation_type=expected_operation_type,
        )


def _normalize_file_list(payload: dict[str, object]) -> dict[str, object]:
    raw_file_items = payload.get("files")
    file_items: list[dict[str, object]] = []
    if isinstance(raw_file_items, list):
        file_items = [item for item in raw_file_items if isinstance(item, dict)]
    return {
        "items": [_normalize_file(item) for item in file_items],
        "next_page_token": payload.get("nextPageToken"),
    }


def _normalize_file(payload: dict[str, object]) -> dict[str, object]:
    mime_type = _nullable_str(payload.get("mimeType"))
    owners = payload.get("owners", [])
    owner_items = []
    if isinstance(owners, list):
        for owner in owners:
            if isinstance(owner, dict):
                owner_items.append(
                    {
                        "display_name": owner.get("displayName"),
                        "email_address": owner.get("emailAddress"),
                    }
                )
    shortcut_details = (
        payload.get("shortcutDetails") if isinstance(payload.get("shortcutDetails"), dict) else {}
    )
    return {
        "id": payload.get("id"),
        "name": payload.get("name"),
        "file_type": _file_type_from_mime_type(mime_type),
        "mime_type": mime_type,
        "parents": payload.get("parents", []),
        "size": payload.get("size"),
        "web_view_link": payload.get("webViewLink"),
        "web_content_link": payload.get("webContentLink"),
        "trashed": payload.get("trashed", False),
        "description": payload.get("description"),
        "created_time": payload.get("createdTime"),
        "modified_time": payload.get("modifiedTime"),
        "owners": owner_items,
        "shortcut_target_id": shortcut_details.get("targetId")
        if isinstance(shortcut_details, dict)
        else None,
    }


def _normalize_permission(payload: dict[str, object]) -> dict[str, object]:
    return {
        "id": payload.get("id"),
        "type": payload.get("type"),
        "role": payload.get("role"),
        "email_address": payload.get("emailAddress"),
        "domain": payload.get("domain"),
        "allow_file_discovery": payload.get("allowFileDiscovery"),
        "display_name": payload.get("displayName"),
    }


def _build_drive_query(
    *,
    text_query: str | None = None,
    exact_name: str | None = None,
    name: str | None = None,
    mime_type: str | None = None,
    parent_id: str | None = None,
    include_trashed: bool = False,
) -> str | None:
    parts: list[str] = []
    if not include_trashed:
        parts.append("trashed = false")
    if parent_id:
        parts.append(f"'{_escape_query_value(parent_id)}' in parents")
    if mime_type:
        parts.append(f"mimeType = '{_escape_query_value(mime_type)}'")
    if exact_name:
        parts.append(f"name = '{_escape_query_value(exact_name)}'")
    if name:
        parts.append(f"name contains '{_escape_query_value(name)}'")
    if text_query:
        escaped = _escape_query_value(text_query)
        parts.append(f"fullText contains '{escaped}'")
    return " and ".join(parts) if parts else None


def _decode_content_payload(payload: object, limit: int = 262144) -> tuple[bytes, str]:
    if not isinstance(payload, dict):
        raise ValidationError("Drive content payload is invalid")
    mime_type = _as_str(payload.get("mime_type"))
    content_text = payload.get("content_text")
    content_base64 = payload.get("content_base64")
    if isinstance(content_text, str):
        _ensure_size_limit(len(content_text), limit)
        content = content_text.encode("utf-8")
        _ensure_size_limit(len(content), limit)
        return content, mime_type
    if isinstance(content_base64, str):
        try:
            _ensure_size_limit(len(content_base64), 4 * ((limit + 2) // 3))
            content = base64.b64decode(content_base64, validate=True)
            _ensure_size_limit(len(content), limit)
            return content, mime_type
        except ValueError as exc:
            raise ValidationError("Drive base64 content is invalid") from exc
    raise ValidationError("Drive content payload is missing inline content")


def _ensure_size_limit(size: int, limit: int) -> None:
    if size > limit:
        raise DriveContentTooLargeError(f"Drive content size {size} exceeds limit {limit}")


def _escape_query_value(value: str) -> str:
    return value.replace("'", "\\'")


def _nullable_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _file_type_from_mime_type(mime_type: str | None) -> str:
    if mime_type is None:
        return "any"
    return MIME_TYPE_TO_FILE_TYPE.get(mime_type, "any")


def _normalize_match_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    collapsed = " ".join(without_marks.casefold().split())
    return collapsed.strip()


def _tokenize_match_text(value: str) -> list[str]:
    normalized = _normalize_match_text(value)
    if not normalized:
        return []
    return [token for token in normalized.split(" ") if token]


def _score_drive_match(
    *,
    item: dict[str, object],
    target_name: str,
    normalized: bool,
    allow_fuzzy: bool,
    required_terms: list[str],
    preferred_terms: list[str],
) -> dict[str, object] | None:
    candidate_name = _nullable_str(item.get("name")) or ""
    candidate_name_normalized = _normalize_match_text(candidate_name)
    target_name_normalized = _normalize_match_text(target_name)
    candidate_terms = set(_tokenize_match_text(candidate_name))
    required_normalized = [
        _normalize_match_text(term) for term in required_terms if _normalize_match_text(term)
    ]
    if required_normalized and not all(term in candidate_terms for term in required_normalized):
        return None

    match_type = "fuzzy"
    score = 0.0
    if candidate_name == target_name and target_name:
        match_type = "exact"
        score = 1.0
    elif (
        normalized
        and candidate_name_normalized == target_name_normalized
        and target_name_normalized
    ):
        match_type = "exact_normalized"
        score = 0.96
    elif target_name_normalized and target_name_normalized in candidate_name_normalized:
        match_type = "partial"
        score = 0.88
    else:
        preferred_normalized = [
            _normalize_match_text(term) for term in preferred_terms if _normalize_match_text(term)
        ]
        matched_terms = sum(1 for term in preferred_normalized if term in candidate_terms)
        if preferred_normalized and matched_terms:
            coverage = matched_terms / len(preferred_normalized)
            score = max(score, 0.7 + (coverage * 0.15))
            match_type = "partial"
        if allow_fuzzy and target_name_normalized and candidate_name_normalized:
            fuzzy_score = SequenceMatcher(
                None, candidate_name_normalized, target_name_normalized
            ).ratio()
            if fuzzy_score >= 0.72:
                score = max(score, round(min(0.84, fuzzy_score), 4))
                if score < 0.85:
                    match_type = "fuzzy"

    if score <= 0.0:
        return None
    result = dict(item)
    result["match_type"] = match_type
    result["score"] = round(score, 4)
    return result


def _sortable_modified_time(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""


def _resolve_match_status(matches: list[dict[str, object]]) -> str:
    if not matches:
        return "not_found"
    if len(matches) == 1:
        return "found"
    top_score = float(matches[0].get("score", 0.0))
    second_score = float(matches[1].get("score", 0.0))
    if top_score >= 0.95 and top_score - second_score >= 0.08:
        return "found"
    return "multiple"


def _build_find_summary(matches: list[dict[str, object]], *, label: str) -> str:
    if not matches:
        return f"No {label.lower()} matches found."
    status = _resolve_match_status(matches)
    if status == "found":
        best = matches[0]
        return f"Best {label.lower()} match is '{best.get('name') or best.get('id')}'."
    return f"Found {len(matches)} candidate {label.lower()} matches."
