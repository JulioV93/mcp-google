from __future__ import annotations

import base64
import io

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from sqlalchemy.orm import Session

from app.config import Settings
from app.google.client_base import GoogleApiClientBase


DRIVE_FILE_FIELDS = (
    "id,name,mimeType,parents,size,webViewLink,webContentLink,trashed,createdTime,modifiedTime,"
    "description,owners(displayName,emailAddress),shortcutDetails,targetId"
)


class DriveClient(GoogleApiClientBase):
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        super().__init__(session, settings)

    def _service(self, *, external_subject: str, tenant_id: str | None = None):
        credentials = self.credentials_provider.get_for_user(
            external_subject=external_subject,
            tenant_id=tenant_id,
        )
        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    def list_files(
        self,
        *,
        external_subject: str,
        tenant_id: str | None = None,
        query: str | None = None,
        page_size: int = 20,
        page_token: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        kwargs: dict[str, object] = {
            "pageSize": page_size,
            "fields": f"nextPageToken, files({DRIVE_FILE_FIELDS})",
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        }
        if query:
            kwargs["q"] = query
        if page_token:
            kwargs["pageToken"] = page_token
        return self._execute(service.files().list(**kwargs))

    def get_file(self, *, external_subject: str, file_id: str, tenant_id: str | None = None) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        return self._execute(
            service.files().get(
                fileId=file_id,
                fields=DRIVE_FILE_FIELDS,
                supportsAllDrives=True,
            )
        )

    def download_file(self, *, external_subject: str, file_id: str, tenant_id: str | None = None) -> bytes:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        def perform_download() -> bytes:
            request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return buffer.getvalue()

        return self._execute_operation(perform_download)

    def export_file(
        self,
        *,
        external_subject: str,
        file_id: str,
        export_mime_type: str,
        tenant_id: str | None = None,
    ) -> bytes:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        def perform_export() -> bytes:
            request = service.files().export_media(fileId=file_id, mimeType=export_mime_type)
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return buffer.getvalue()

        return self._execute_operation(perform_export)

    def create_folder(
        self,
        *,
        external_subject: str,
        name: str,
        parent_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        body: dict[str, object] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            body["parents"] = [parent_id]
        return self._execute(service.files().create(body=body, fields=DRIVE_FILE_FIELDS, supportsAllDrives=True))

    def create_shortcut(
        self,
        *,
        external_subject: str,
        name: str,
        target_file_id: str,
        parent_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        body: dict[str, object] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.shortcut",
            "shortcutDetails": {"targetId": target_file_id},
        }
        if parent_id:
            body["parents"] = [parent_id]
        return self._execute(service.files().create(body=body, fields=DRIVE_FILE_FIELDS, supportsAllDrives=True))

    def update_metadata(
        self,
        *,
        external_subject: str,
        file_id: str,
        metadata_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        return self._execute(
            service.files().update(
                fileId=file_id,
                body=metadata_body,
                fields=DRIVE_FILE_FIELDS,
                supportsAllDrives=True,
            )
        )

    def move_file(
        self,
        *,
        external_subject: str,
        file_id: str,
        add_parent_id: str | None = None,
        remove_parent_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        kwargs: dict[str, object] = {
            "fileId": file_id,
            "fields": DRIVE_FILE_FIELDS,
            "supportsAllDrives": True,
        }
        if add_parent_id:
            kwargs["addParents"] = add_parent_id
        if remove_parent_id:
            kwargs["removeParents"] = remove_parent_id
        return self._execute(service.files().update(**kwargs))

    def upload_file(
        self,
        *,
        external_subject: str,
        name: str,
        mime_type: str,
        content_bytes: bytes,
        parent_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        body: dict[str, object] = {"name": name}
        if parent_id:
            body["parents"] = [parent_id]
        media = MediaIoBaseUpload(io.BytesIO(content_bytes), mimetype=mime_type, resumable=False)
        return self._execute(
            service.files().create(
                body=body,
                media_body=media,
                fields=DRIVE_FILE_FIELDS,
                supportsAllDrives=True,
            )
        )

    def update_file_content(
        self,
        *,
        external_subject: str,
        file_id: str,
        mime_type: str,
        content_bytes: bytes,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        media = MediaIoBaseUpload(io.BytesIO(content_bytes), mimetype=mime_type, resumable=False)
        return self._execute(
            service.files().update(
                fileId=file_id,
                media_body=media,
                fields=DRIVE_FILE_FIELDS,
                supportsAllDrives=True,
            )
        )

    def trash_file(self, *, external_subject: str, file_id: str, tenant_id: str | None = None) -> dict[str, object]:
        return self.update_metadata(
            external_subject=external_subject,
            file_id=file_id,
            metadata_body={"trashed": True},
            tenant_id=tenant_id,
        )

    def delete_file_permanently(
        self,
        *,
        external_subject: str,
        file_id: str,
        tenant_id: str | None = None,
    ) -> None:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        self._execute(service.files().delete(fileId=file_id, supportsAllDrives=True))

    def list_permissions(
        self,
        *,
        external_subject: str,
        file_id: str,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        return self._execute(
            service.permissions().list(
                fileId=file_id,
                fields="permissions(id,type,role,emailAddress,domain,allowFileDiscovery,displayName)",
                supportsAllDrives=True,
            )
        )

    def create_permission(
        self,
        *,
        external_subject: str,
        file_id: str,
        permission_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        return self._execute(
            service.permissions().create(
                fileId=file_id,
                body=permission_body,
                fields="id,type,role,emailAddress,domain,allowFileDiscovery,displayName",
                supportsAllDrives=True,
                sendNotificationEmail=False,
            )
        )

    def delete_permission(
        self,
        *,
        external_subject: str,
        file_id: str,
        permission_id: str,
        tenant_id: str | None = None,
    ) -> None:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        self._execute(
            service.permissions().delete(
                fileId=file_id,
                permissionId=permission_id,
                supportsAllDrives=True,
            )
        )


def encode_bytes_to_base64(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")
