from __future__ import annotations

from fastmcp import FastMCP

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
        """List Drive files for the current user."""
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
        """Search Drive files for the current user."""
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
        """Get Drive file metadata by ID."""
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
        """List Drive permissions for a file."""
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
        """Download a non-native Drive file as base64 content."""
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
        """Export a native Google Workspace file to a supported format."""
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
        """Create a Drive folder."""
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
    def drive_create_shortcut(name: str, target_file_id: str, parent_id: str | None = None) -> dict[str, object]:
        """Create a Drive shortcut."""
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
        """Update safe Drive metadata such as name and description."""
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
        """Move a Drive file between folders."""
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
        """Prepare a sensitive Drive upload operation."""
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
        """Confirm a prepared Drive upload operation."""
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
        """Prepare a sensitive Drive file content save operation."""
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
    def drive_confirm_save_file(operation_id: str) -> dict[str, object]:
        """Confirm a prepared Drive file save operation."""
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
        """Prepare a sensitive Drive delete operation."""
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
        """Confirm a prepared Drive delete operation."""
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
        """Prepare a sensitive Drive sharing operation."""
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
        """Confirm a prepared Drive sharing operation."""
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
        """Prepare a sensitive Drive permission revocation operation."""
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
        """Confirm a prepared Drive permission revocation operation."""
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
