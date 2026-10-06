from __future__ import annotations

import base64
import io

from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import DriveContentTooLargeError
from app.google.client_base import GoogleApiClientBase

DRIVE_FILE_FIELDS = (
    "id,name,mimeType,parents,size,webViewLink,webContentLink,trashed,createdTime,modifiedTime,"
    "description,owners(displayName,emailAddress),shortcutDetails(targetId)"
)


class DriveClient(GoogleApiClientBase):
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        super().__init__(session, settings)

    def _service(self, *, external_subject: str, tenant_id: str | None = None):
        return self._get_service(
            "drive", "v3", external_subject=external_subject, tenant_id=tenant_id
        )

    def _docs_service(self, *, external_subject: str, tenant_id: str | None = None):
        return self._get_service(
            "docs", "v1", external_subject=external_subject, tenant_id=tenant_id
        )

    def _sheets_service(self, *, external_subject: str, tenant_id: str | None = None):
        return self._get_service(
            "sheets", "v4", external_subject=external_subject, tenant_id=tenant_id
        )

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

    def get_file(
        self, *, external_subject: str, file_id: str, tenant_id: str | None = None
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        return self._execute(
            service.files().get(
                fileId=file_id,
                fields=DRIVE_FILE_FIELDS,
                supportsAllDrives=True,
            )
        )

    def download_file(
        self, *, external_subject: str, file_id: str, tenant_id: str | None = None
    ) -> bytes:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)

        def perform_download() -> bytes:
            request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
            buffer = LimitedDownloadBuffer(self.settings.drive_inline_content_limit_bytes)
            downloader = MediaIoBaseDownload(buffer, request, chunksize=65536)
            done = False
            while not done:
                _, done = downloader.next_chunk()
                if buffer.tell() > self.settings.drive_inline_content_limit_bytes:
                    raise DriveContentTooLargeError()
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
            buffer = LimitedDownloadBuffer(self.settings.drive_inline_content_limit_bytes)
            downloader = MediaIoBaseDownload(buffer, request, chunksize=65536)
            done = False
            while not done:
                _, done = downloader.next_chunk()
                if buffer.tell() > self.settings.drive_inline_content_limit_bytes:
                    raise DriveContentTooLargeError()
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
        return self._execute(
            service.files().create(body=body, fields=DRIVE_FILE_FIELDS, supportsAllDrives=True)
        )

    def create_native_file(
        self,
        *,
        external_subject: str,
        name: str,
        mime_type: str,
        parent_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        body: dict[str, object] = {
            "name": name,
            "mimeType": mime_type,
        }
        if parent_id:
            body["parents"] = [parent_id]
        return self._execute(
            service.files().create(body=body, fields=DRIVE_FILE_FIELDS, supportsAllDrives=True)
        )

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
        return self._execute(
            service.files().create(body=body, fields=DRIVE_FILE_FIELDS, supportsAllDrives=True)
        )

    def write_google_doc(
        self,
        *,
        external_subject: str,
        file_id: str,
        content_text: str,
        mode: str,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        self.session.info["diagnostic_stage"] = "docs_read_document"
        service = self._docs_service(external_subject=external_subject, tenant_id=tenant_id)
        document = self._execute(service.documents().get(documentId=file_id))
        body_content = (
            document.get("body", {}).get("content", []) if isinstance(document, dict) else []
        )
        current_end_index = 1
        if isinstance(body_content, list):
            for item in body_content:
                if isinstance(item, dict):
                    end_index = item.get("endIndex")
                    if isinstance(end_index, int) and end_index > current_end_index:
                        current_end_index = end_index
        requests: list[dict[str, object]] = []
        if mode == "replace" and current_end_index > 1:
            requests.append(
                {
                    "deleteContentRange": {
                        "range": {
                            "startIndex": 1,
                            "endIndex": max(1, current_end_index - 1),
                        }
                    }
                }
            )
            insert_index = 1
        else:
            insert_index = max(1, current_end_index - 1)
            if mode == "append" and insert_index > 1 and not content_text.startswith("\n"):
                content_text = "\n" + content_text
        requests.append({"insertText": {"location": {"index": insert_index}, "text": content_text}})
        self.session.info["diagnostic_stage"] = "docs_batch_update"
        return self._execute(
            service.documents().batchUpdate(
                documentId=file_id,
                body={"requests": requests},
            )
        )

    def write_google_sheet(
        self,
        *,
        external_subject: str,
        file_id: str,
        values: list[list[str | int | float | bool | None]],
        sheet_name: str | None,
        create_sheet_if_missing: bool,
        start_cell: str,
        mode: str,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._sheets_service(external_subject=external_subject, tenant_id=tenant_id)
        target_sheet_name = self._resolve_sheet_name(
            external_subject=external_subject,
            file_id=file_id,
            sheet_name=sheet_name,
            create_sheet_if_missing=create_sheet_if_missing,
            tenant_id=tenant_id,
        )
        value_range = {"values": values}
        range_name = f"{target_sheet_name}!{start_cell}"
        if mode == "append":
            return self._execute(
                service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=file_id,
                    range=range_name,
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body=value_range,
                )
            )
        return self._execute(
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=file_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=value_range,
            )
        )

    def _resolve_sheet_name(
        self,
        *,
        external_subject: str,
        file_id: str,
        sheet_name: str | None,
        create_sheet_if_missing: bool,
        tenant_id: str | None = None,
    ) -> str:
        service = self._sheets_service(external_subject=external_subject, tenant_id=tenant_id)
        spreadsheet = self._execute(
            service.spreadsheets().get(
                spreadsheetId=file_id,
                fields="sheets(properties(title))",
            )
        )
        sheets = spreadsheet.get("sheets", []) if isinstance(spreadsheet, dict) else []
        titles: list[str] = []
        if isinstance(sheets, list):
            for item in sheets:
                if isinstance(item, dict):
                    properties = item.get("properties", {})
                    if isinstance(properties, dict):
                        title = properties.get("title")
                        if isinstance(title, str) and title:
                            titles.append(title)
        if sheet_name:
            if sheet_name in titles:
                return sheet_name
            if create_sheet_if_missing:
                self._execute(
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=file_id,
                        body={
                            "requests": [
                                {
                                    "addSheet": {
                                        "properties": {
                                            "title": sheet_name,
                                        }
                                    }
                                }
                            ]
                        },
                    )
                )
                return sheet_name
        if titles:
            return titles[0]
        return "Sheet1"

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

    def trash_file(
        self, *, external_subject: str, file_id: str, tenant_id: str | None = None
    ) -> dict[str, object]:
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


class LimitedDownloadBuffer(io.BytesIO):
    def __init__(self, limit: int):
        super().__init__()
        self.limit = limit

    def write(self, value):
        if self.tell() + len(value) > self.limit:
            raise DriveContentTooLargeError()
        return super().write(value)
