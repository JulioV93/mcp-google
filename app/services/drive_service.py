from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import PendingGoogleOperation
from app.db.repositories.pending_google_operations import PendingGoogleOperationRepository
from app.errors import (
    AppError,
    DriveContentTooLargeError,
    DriveExportNotSupportedError,
    DriveNativeEditNotSupportedError,
    DriveOperationConsumedError,
    DriveOperationExpiredError,
    DriveOperationNotFoundError,
    DrivePayloadMismatchError,
    ValidationError,
)
from app.google.drive_client import DriveClient, encode_bytes_to_base64
from app.schemas.drive import (
    DriveConfirmOperationInput,
    DriveCreateFolderInput,
    DriveCreateShortcutInput,
    DriveDownloadFileInput,
    DriveExportFileInput,
    DriveGetFileInput,
    DriveListFilesInput,
    DriveListPermissionsInput,
    DriveMoveFileInput,
    DrivePrepareDeleteFileInput,
    DrivePrepareRevokePermissionInput,
    DrivePrepareSaveFileInput,
    DrivePrepareShareFileInput,
    DrivePrepareUploadInput,
    DriveSearchFilesInput,
    DriveUpdateMetadataInput,
    estimate_inline_bytes,
    is_google_native_mime_type,
)
from app.services.connection_service import ConnectionService


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
        try:
            payload = self.client.list_files(
                external_subject=external_subject,
                tenant_id=tenant_id,
                query=_build_drive_query(parent_id=input_data.parent_id, include_trashed=input_data.include_trashed),
                page_size=input_data.page_size,
                page_token=input_data.page_token,
            )
        except AppError:
            raise
        return _normalize_file_list(payload)

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
        try:
            payload = self.client.list_files(
                external_subject=external_subject,
                tenant_id=tenant_id,
                query=query,
                page_size=input_data.page_size,
                page_token=input_data.page_token,
            )
        except AppError:
            raise
        return _normalize_file_list(payload)

    def get_file(
        self,
        *,
        external_subject: str,
        input_data: DriveGetFileInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.get_file(
                external_subject=external_subject,
                tenant_id=tenant_id,
                file_id=input_data.file_id,
            )
        except AppError:
            raise
        return _normalize_file(payload)

    def list_permissions(
        self,
        *,
        external_subject: str,
        input_data: DriveListPermissionsInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        try:
            payload = self.client.list_permissions(
                external_subject=external_subject,
                tenant_id=tenant_id,
                file_id=input_data.file_id,
            )
        except AppError:
            raise
        items = [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "role": item.get("role"),
                "email_address": item.get("emailAddress"),
                "domain": item.get("domain"),
                "allow_file_discovery": item.get("allowFileDiscovery"),
                "display_name": item.get("displayName"),
            }
            for item in payload.get("permissions", [])
        ]
        return {"file_id": input_data.file_id, "items": items}

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
            raise DriveNativeEditNotSupportedError("Use drive_export_file for native Google Workspace files")
        content = self.client.download_file(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=input_data.file_id,
        )
        _ensure_size_limit(len(content), self.settings.drive_inline_content_limit_bytes)
        return {
            "file": metadata,
            "content_base64": encode_bytes_to_base64(content),
            "content_size": len(content),
        }

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
        return {
            "file": metadata,
            "export_mime_type": input_data.export_mime_type,
            "content_base64": encode_bytes_to_base64(content),
            "content_size": len(content),
        }

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
        return _normalize_file(payload)

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
        return _normalize_file(payload)

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
        return _normalize_file(payload)

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
        return _normalize_file(payload)

    def prepare_upload(
        self,
        *,
        external_subject: str,
        input_data: DrivePrepareUploadInput,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        size = estimate_inline_bytes(input_data.content)
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
        content_bytes, mime_type = _decode_content_payload(payload.get("content", {}))
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
        return {
            "operation_id": input_data.operation_id,
            "confirmed": True,
            "file": _normalize_file(result),
        }

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
        size = estimate_inline_bytes(input_data.content)
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
        content_bytes, mime_type = _decode_content_payload(payload.get("content", {}))
        result = self.client.update_file_content(
            external_subject=external_subject,
            tenant_id=tenant_id,
            file_id=file_id,
            mime_type=mime_type,
            content_bytes=content_bytes,
        )
        self.pending_operations.mark_confirmed(record)
        self.session.commit()
        return {
            "operation_id": input_data.operation_id,
            "confirmed": True,
            "file": _normalize_file(result),
        }

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
        return {"operation_id": input_data.operation_id, "confirmed": True, **result}

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
        return {
            "operation_id": input_data.operation_id,
            "confirmed": True,
            "file_id": file_id,
            "permission": _normalize_permission(result),
        }

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
        return {
            "operation_id": input_data.operation_id,
            "confirmed": True,
            "file_id": file_id,
            "permission_id": permission_id,
            "revoked": True,
        }

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
        user = self.connections.get_or_create_user(external_subject=external_subject, tenant_id=tenant_id)
        operation_key = secrets.token_urlsafe(24)
        payload_hash = _hash_payload(payload_normalized)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.settings.drive_confirmation_ttl_seconds)
        record = self.pending_operations.create(
            user_id=user.id,
            provider="google",
            operation_key=operation_key,
            operation_type=operation_type,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            payload_normalized=payload_normalized,
            payload_hash=payload_hash,
            expires_at=expires_at,
        )
        self.session.commit()
        return record

    def _get_pending_operation(
        self,
        *,
        external_subject: str,
        tenant_id: str | None,
        operation_id: str,
        expected_operation_type: str,
    ) -> PendingGoogleOperation:
        user = self.connections.get_or_create_user(external_subject=external_subject, tenant_id=tenant_id)
        record = self.pending_operations.get_by_operation_key(operation_id)
        if record is None or record.user_id != user.id:
            raise DriveOperationNotFoundError()
        if record.operation_type != expected_operation_type:
            raise DriveOperationNotFoundError("Drive confirmation operation type does not match")
        if record.status == "confirmed":
            raise DriveOperationConsumedError()
        if record.status != "pending":
            raise DriveOperationNotFoundError("Drive confirmation operation is no longer pending")
        if _is_expired(record.expires_at):
            self.pending_operations.mark_expired(record)
            self.session.commit()
            raise DriveOperationExpiredError()
        if record.payload_hash != _hash_payload(record.payload_normalized):
            raise DrivePayloadMismatchError()
        return record


def _normalize_file_list(payload: dict[str, object]) -> dict[str, object]:
    return {
        "items": [_normalize_file(item) for item in payload.get("files", [])],
        "next_page_token": payload.get("nextPageToken"),
    }


def _normalize_file(payload: dict[str, object]) -> dict[str, object]:
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
    shortcut_details = payload.get("shortcutDetails") if isinstance(payload.get("shortcutDetails"), dict) else {}
    return {
        "id": payload.get("id"),
        "name": payload.get("name"),
        "mime_type": payload.get("mimeType"),
        "parents": payload.get("parents", []),
        "size": payload.get("size"),
        "web_view_link": payload.get("webViewLink"),
        "web_content_link": payload.get("webContentLink"),
        "trashed": payload.get("trashed", False),
        "description": payload.get("description"),
        "created_time": payload.get("createdTime"),
        "modified_time": payload.get("modifiedTime"),
        "owners": owner_items,
        "shortcut_target_id": shortcut_details.get("targetId") if isinstance(shortcut_details, dict) else None,
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


def _preview_from_record(
    record: PendingGoogleOperation,
    *,
    risk_level: str,
    summary: dict[str, object],
) -> dict[str, object]:
    return {
        "operation_id": record.operation_key,
        "operation_type": record.operation_type,
        "resource_type": record.resource_type,
        "resource_id": record.resource_id,
        "resource_name": record.resource_name,
        "expires_at": record.expires_at.isoformat(),
        "requires_confirmation": True,
        "risk_level": risk_level,
        "summary": summary,
    }


def _build_drive_query(
    *,
    text_query: str | None = None,
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
    if name:
        parts.append(f"name contains '{_escape_query_value(name)}'")
    if text_query:
        escaped = _escape_query_value(text_query)
        parts.append(f"fullText contains '{escaped}'")
    return " and ".join(parts) if parts else None


def _decode_content_payload(payload: object) -> tuple[bytes, str]:
    if not isinstance(payload, dict):
        raise ValidationError("Drive content payload is invalid")
    mime_type = _as_str(payload.get("mime_type"))
    content_text = payload.get("content_text")
    content_base64 = payload.get("content_base64")
    if isinstance(content_text, str):
        return content_text.encode("utf-8"), mime_type
    if isinstance(content_base64, str):
        try:
            return base64.b64decode(content_base64), mime_type
        except ValueError as exc:
            raise ValidationError("Drive base64 content is invalid") from exc
    raise ValidationError("Drive content payload is missing inline content")


def _ensure_size_limit(size: int, limit: int) -> None:
    if size > limit:
        raise DriveContentTooLargeError(f"Drive content size {size} exceeds limit {limit}")


def _hash_payload(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_expired(value: datetime) -> bool:
    current = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= current


def _escape_query_value(value: str) -> str:
    return value.replace("'", "\\'")


def _as_str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError("Expected a non-empty string value")
    return value


def _nullable_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
