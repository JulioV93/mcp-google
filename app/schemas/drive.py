from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


GOOGLE_NATIVE_MIME_PREFIX = "application/vnd.google-apps."


class DriveListFilesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_size: int = Field(default=20, ge=1, le=100)
    page_token: str | None = None
    parent_id: str | None = None
    include_trashed: bool = False


class DriveSearchFilesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    name: str | None = None
    mime_type: str | None = None
    parent_id: str | None = None
    page_size: int = Field(default=20, ge=1, le=100)
    page_token: str | None = None
    include_trashed: bool = False


class DriveGetFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str


class DriveDownloadFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str


class DriveExportFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    export_mime_type: str


class DriveCreateFolderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    parent_id: str | None = None


class DriveCreateShortcutInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    target_file_id: str
    parent_id: str | None = None


class DriveUpdateMetadataInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_changes(self) -> "DriveUpdateMetadataInput":
        if self.name is None and self.description is None:
            raise ValueError("At least one metadata field must be provided")
        return self


class DriveMoveFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    add_parent_id: str | None = None
    remove_parent_id: str | None = None

    @model_validator(mode="after")
    def validate_move(self) -> "DriveMoveFileInput":
        if self.add_parent_id is None and self.remove_parent_id is None:
            raise ValueError("At least one parent change must be provided")
        return self


class DriveInlineContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_text: str | None = None
    content_base64: str | None = None
    mime_type: str

    @model_validator(mode="after")
    def validate_content(self) -> "DriveInlineContentInput":
        if bool(self.content_text) == bool(self.content_base64):
            raise ValueError("Exactly one of content_text or content_base64 is required")
        return self


class DrivePrepareUploadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    parent_id: str | None = None
    content: DriveInlineContentInput


class DrivePrepareSaveFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    content: DriveInlineContentInput


class DrivePrepareDeleteFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    permanent: bool = False


class DrivePermissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(pattern="^(user|group|domain|anyone)$")
    role: str = Field(pattern="^(owner|organizer|fileOrganizer|writer|commenter|reader)$")
    email_address: str | None = None
    domain: str | None = None
    allow_file_discovery: bool | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "DrivePermissionInput":
        if self.type in {"user", "group"} and self.email_address is None:
            raise ValueError("email_address is required for user and group permissions")
        if self.type == "domain" and not self.domain:
            raise ValueError("domain is required for domain permissions")
        if self.email_address is not None and "@" not in self.email_address:
            raise ValueError("email_address must be a valid email")
        return self


class DrivePrepareShareFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    permission: DrivePermissionInput


class DrivePrepareRevokePermissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    permission_id: str


class DriveConfirmOperationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str


class DriveListPermissionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str


class DriveOperationPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    operation_type: str
    resource_type: str
    resource_id: str | None = None
    resource_name: str | None = None
    expires_at: str
    requires_confirmation: bool = True
    risk_level: str
    summary: dict[str, object]


def is_google_native_mime_type(mime_type: str | None) -> bool:
    return bool(mime_type and mime_type.startswith(GOOGLE_NATIVE_MIME_PREFIX))


def estimate_inline_bytes(content: DriveInlineContentInput) -> int:
    if content.content_text is not None:
        return len(content.content_text.encode("utf-8"))
    if content.content_base64 is not None:
        return len(content.content_base64.encode("ascii"))
    return 0
