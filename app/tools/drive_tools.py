from __future__ import annotations

from fastmcp import FastMCP

from app.schemas.drive import (
    DriveConfirmOperationInput,
    DriveCreateFolderInput,
    DriveCreateNativeFileInput,
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
    DrivePrepareWriteGoogleDocInput,
    DrivePrepareWriteGoogleSheetInput,
    DrivePrepareUploadInput,
    DriveSearchFilesInput,
    DriveUpdateMetadataInput,
)
from app.services.drive_service import DriveService
from app.tools.common import run_tool


def register_drive_tools(mcp: FastMCP) -> None:
    @mcp.tool
    def drive_list_files(
        page_size: int = 20,
        page_token: str | None = None,
        parent_id: str | None = None,
        include_trashed: bool = False,
    ) -> dict[str, object]:
        """List Drive files for the current user.

        Use to browse files or folders when there is no precise search term yet.
        """
        payload = DriveListFilesInput(
            page_size=page_size,
            page_token=page_token,
            parent_id=parent_id,
            include_trashed=include_trashed,
        )
        return run_tool(
            tool_name="drive_list_files",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).list_files(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_search_files(
        query: str | None = None,
        name: str | None = None,
        mime_type: str | None = None,
        parent_id: str | None = None,
        page_size: int = 20,
        page_token: str | None = None,
        include_trashed: bool = False,
    ) -> dict[str, object]:
        """Search Drive files for the current user.

        Use before move, share, save, or delete when the file identity is uncertain.
        Prefer this over mutation tools when you do not yet know `file_id`.
        """
        payload = DriveSearchFilesInput(
            query=query,
            name=name,
            mime_type=mime_type,
            parent_id=parent_id,
            page_size=page_size,
            page_token=page_token,
            include_trashed=include_trashed,
        )
        return run_tool(
            tool_name="drive_search_files",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).search_files(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_get_file(file_id: str) -> dict[str, object]:
        """Get Drive file metadata by ID.

        Use after search or list when you need exact metadata for a known file.
        """
        payload = DriveGetFileInput(file_id=file_id)
        return run_tool(
            tool_name="drive_get_file",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).get_file(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_list_permissions(file_id: str) -> dict[str, object]:
        """List Drive permissions for a file.

        Use before sharing changes or revoking access when you need the current permission state.
        """
        payload = DriveListPermissionsInput(file_id=file_id)
        return run_tool(
            tool_name="drive_list_permissions",
            provider="google",
            resource_type="drive_permission",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).list_permissions(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_download_file(file_id: str) -> dict[str, object]:
        """Download a non-native Drive file as base64 content.

        Use only for non-native files such as PDFs or uploaded binaries.
        For Google Docs, Sheets, or Slides, use `drive_export_file` instead.
        """
        payload = DriveDownloadFileInput(file_id=file_id)
        return run_tool(
            tool_name="drive_download_file",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).download_file(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_export_file(file_id: str, export_mime_type: str) -> dict[str, object]:
        """Export a native Google Workspace file to a supported format.

        Use this for Google Docs, Sheets, and Slides when you need file contents.
        """
        payload = DriveExportFileInput(file_id=file_id, export_mime_type=export_mime_type)
        return run_tool(
            tool_name="drive_export_file",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).export_file(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_create_folder(name: str, parent_id: str | None = None) -> dict[str, object]:
        """Create a Drive folder.

        Use to create a new container for files or shortcuts.
        """
        payload = DriveCreateFolderInput(name=name, parent_id=parent_id)
        return run_tool(
            tool_name="drive_create_folder",
            provider="google",
            resource_type="drive_folder",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).create_folder(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_create_google_doc(name: str, parent_id: str | None = None) -> dict[str, object]:
        """Create a native Google Doc in Drive.

        Use when the user explicitly wants a new Google Docs document, not a binary upload.
        """
        payload = DriveCreateNativeFileInput(name=name, parent_id=parent_id)
        return run_tool(
            tool_name="drive_create_google_doc",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).create_google_doc(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_create_google_sheet(name: str, parent_id: str | None = None) -> dict[str, object]:
        """Create a native Google Sheet in Drive.

        Use when the user explicitly wants a new Google Sheets spreadsheet.
        """
        payload = DriveCreateNativeFileInput(name=name, parent_id=parent_id)
        return run_tool(
            tool_name="drive_create_google_sheet",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).create_google_sheet(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_create_google_slide(name: str, parent_id: str | None = None) -> dict[str, object]:
        """Create a native Google Slides presentation in Drive.

        Use when the user explicitly wants a new Google Slides deck.
        """
        payload = DriveCreateNativeFileInput(name=name, parent_id=parent_id)
        return run_tool(
            tool_name="drive_create_google_slide",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).create_google_slide(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_create_shortcut(name: str, target_file_id: str, parent_id: str | None = None) -> dict[str, object]:
        """Create a Drive shortcut.

        Use when the user wants another folder entry pointing at an existing file.
        """
        payload = DriveCreateShortcutInput(name=name, target_file_id=target_file_id, parent_id=parent_id)
        return run_tool(
            tool_name="drive_create_shortcut",
            provider="google",
            resource_type="drive_shortcut",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).create_shortcut(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_update_metadata(
        file_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> dict[str, object]:
        """Update safe Drive metadata such as name and description.

        Use for non-destructive metadata changes. This does not change file contents.
        """
        payload = DriveUpdateMetadataInput(file_id=file_id, name=name, description=description)
        return run_tool(
            tool_name="drive_update_metadata",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).update_metadata(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_move_file(
        file_id: str,
        add_parent_id: str | None = None,
        remove_parent_id: str | None = None,
    ) -> dict[str, object]:
        """Move a Drive file between folders.

        Use only when you know the file ID and parent changes.
        Search first if the file identity is uncertain.
        """
        payload = DriveMoveFileInput(file_id=file_id, add_parent_id=add_parent_id, remove_parent_id=remove_parent_id)
        return run_tool(
            tool_name="drive_move_file",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).move_file(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_prepare_upload(name: str, content: dict[str, object], parent_id: str | None = None) -> dict[str, object]:
        """Prepare a sensitive Drive upload operation.

        This does not upload yet. It creates a preview and operation_id for later confirmation.
        """
        payload = DrivePrepareUploadInput.model_validate({"name": name, "parent_id": parent_id, "content": content})
        return run_tool(
            tool_name="drive_prepare_upload",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).prepare_upload(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_confirm_upload(operation_id: str) -> dict[str, object]:
        """Confirm a prepared Drive upload operation.

        Use only after reviewing a prior `drive_prepare_upload` preview.
        """
        payload = DriveConfirmOperationInput(operation_id=operation_id)
        return run_tool(
            tool_name="drive_confirm_upload",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).confirm_upload(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_prepare_save_file(file_id: str, content: dict[str, object]) -> dict[str, object]:
        """Prepare a sensitive Drive file content save operation.

        This does not save yet. It validates and previews a later file content update.
        """
        payload = DrivePrepareSaveFileInput.model_validate({"file_id": file_id, "content": content})
        return run_tool(
            tool_name="drive_prepare_save_file",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).prepare_save_file(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_prepare_write_google_doc(file_id: str, content_text: str, mode: str = "replace") -> dict[str, object]:
        """Prepare writing text content into a native Google Doc.

        Use this instead of binary save when the target file is a Google Docs document.
        """
        payload = DrivePrepareWriteGoogleDocInput(file_id=file_id, content_text=content_text, mode=mode)
        return run_tool(
            tool_name="drive_prepare_write_google_doc",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).prepare_write_google_doc(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_confirm_write_google_doc(operation_id: str) -> dict[str, object]:
        """Confirm a prepared write operation for a native Google Doc."""
        payload = DriveConfirmOperationInput(operation_id=operation_id)
        return run_tool(
            tool_name="drive_confirm_write_google_doc",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).confirm_write_google_doc(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_prepare_write_google_sheet(
        file_id: str,
        values: list[list[str | int | float | bool | None]],
        sheet_name: str | None = None,
        create_sheet_if_missing: bool = False,
        start_cell: str = "A1",
        mode: str = "overwrite",
    ) -> dict[str, object]:
        """Prepare writing tabular data into a native Google Sheet.

        Use this for structured rows and columns instead of binary save.
        """
        payload = DrivePrepareWriteGoogleSheetInput(
            file_id=file_id,
            values=values,
            sheet_name=sheet_name,
            create_sheet_if_missing=create_sheet_if_missing,
            start_cell=start_cell,
            mode=mode,
        )
        return run_tool(
            tool_name="drive_prepare_write_google_sheet",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).prepare_write_google_sheet(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_confirm_write_google_sheet(operation_id: str) -> dict[str, object]:
        """Confirm a prepared write operation for a native Google Sheet."""
        payload = DriveConfirmOperationInput(operation_id=operation_id)
        return run_tool(
            tool_name="drive_confirm_write_google_sheet",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).confirm_write_google_sheet(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_prepare_upload_markdown(name: str, content_markdown: str, parent_id: str | None = None) -> dict[str, object]:
        """Prepare uploading a Markdown file directly to Drive.

        Use this when the user wants a `.md` file stored in Drive as a regular file.
        """
        payload = DrivePrepareUploadInput.model_validate(
            {
                "name": name,
                "parent_id": parent_id,
                "content": {
                    "content_text": content_markdown,
                    "mime_type": "text/markdown",
                },
            }
        )
        return run_tool(
            tool_name="drive_prepare_upload_markdown",
            provider="google",
            resource_type="drive_file",
            arguments={"name": name, "parent_id": parent_id, "content_markdown": content_markdown},
            operation=lambda session, context: DriveService(session).prepare_upload(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_confirm_save_file(operation_id: str) -> dict[str, object]:
        """Confirm a prepared Drive file save operation.

        Use only after reviewing a prior `drive_prepare_save_file` preview.
        """
        payload = DriveConfirmOperationInput(operation_id=operation_id)
        return run_tool(
            tool_name="drive_confirm_save_file",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).confirm_save_file(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_prepare_delete_file(file_id: str, permanent: bool = False) -> dict[str, object]:
        """Prepare a sensitive Drive delete operation.

        This does not delete yet. It previews trash or permanent delete and returns an operation_id.
        """
        payload = DrivePrepareDeleteFileInput(file_id=file_id, permanent=permanent)
        return run_tool(
            tool_name="drive_prepare_delete_file",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).prepare_delete_file(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_confirm_delete_file(operation_id: str) -> dict[str, object]:
        """Confirm a prepared Drive delete operation.

        Use only after reviewing a prior `drive_prepare_delete_file` preview.
        """
        payload = DriveConfirmOperationInput(operation_id=operation_id)
        return run_tool(
            tool_name="drive_confirm_delete_file",
            provider="google",
            resource_type="drive_file",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).confirm_delete_file(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_prepare_share_file(file_id: str, permission: dict[str, object]) -> dict[str, object]:
        """Prepare a sensitive Drive sharing operation.

        This does not share yet. It previews the permission change and returns an operation_id.
        """
        payload = DrivePrepareShareFileInput.model_validate({"file_id": file_id, "permission": permission})
        return run_tool(
            tool_name="drive_prepare_share_file",
            provider="google",
            resource_type="drive_permission",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).prepare_share_file(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_confirm_share_file(operation_id: str) -> dict[str, object]:
        """Confirm a prepared Drive sharing operation.

        Use only after reviewing a prior `drive_prepare_share_file` preview.
        """
        payload = DriveConfirmOperationInput(operation_id=operation_id)
        return run_tool(
            tool_name="drive_confirm_share_file",
            provider="google",
            resource_type="drive_permission",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).confirm_share_file(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_prepare_revoke_permission(file_id: str, permission_id: str) -> dict[str, object]:
        """Prepare a sensitive Drive permission revocation operation.

        This does not revoke yet. It previews the change and returns an operation_id.
        """
        payload = DrivePrepareRevokePermissionInput(file_id=file_id, permission_id=permission_id)
        return run_tool(
            tool_name="drive_prepare_revoke_permission",
            provider="google",
            resource_type="drive_permission",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).prepare_revoke_permission(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )

    @mcp.tool
    def drive_confirm_revoke_permission(operation_id: str) -> dict[str, object]:
        """Confirm a prepared Drive permission revocation operation.

        Use only after reviewing a prior `drive_prepare_revoke_permission` preview.
        """
        payload = DriveConfirmOperationInput(operation_id=operation_id)
        return run_tool(
            tool_name="drive_confirm_revoke_permission",
            provider="google",
            resource_type="drive_permission",
            arguments=payload.model_dump(exclude_none=True),
            operation=lambda session, context: DriveService(session).confirm_revoke_permission(
                external_subject=context.subject,
                tenant_id=context.tenant_id,
                input_data=payload,
            ),
        )
