from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

GOOGLE_NATIVE_MIME_PREFIX = "application/vnd.google-apps."


class DriveListFilesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_size: int = Field(
        default=20, ge=1, le=100, description="Maximum number of files to return."
    )
    page_token: str | None = Field(
        default=None, description="Pagination token from a previous list response."
    )
    parent_id: str | None = Field(
        default=None, description="Optional parent folder ID to scope the listing."
    )
    include_trashed: bool = Field(
        default=False, description="Whether trashed files should be included."
    )


class DriveSearchFilesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, description="Full-text Drive search query.")
    name: str | None = Field(default=None, description="Partial file name to search for.")
    mime_type: str | None = Field(default=None, description="Optional exact mime type filter.")
    parent_id: str | None = Field(default=None, description="Optional parent folder ID filter.")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Maximum number of files to return."
    )
    page_token: str | None = Field(
        default=None, description="Pagination token from a previous search response."
    )
    include_trashed: bool = Field(
        default=False, description="Whether trashed files should be included."
    )


class DriveFindByNameInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Target Drive file or folder name.")
    exact: bool = Field(
        default=False, description="Whether to prioritize exact name matches first."
    )
    normalized: bool = Field(
        default=True,
        description="Whether to compare normalized names locally using lowercase, trimmed, accent-free text.",
    )
    include_trashed: bool = Field(
        default=False, description="Whether trashed files should be included."
    )
    parent_id: str | None = Field(default=None, description="Optional parent folder ID filter.")
    max_results: int = Field(
        default=20, ge=1, le=100, description="Maximum number of ranked matches to return."
    )


class DriveFindFolderByNameInput(DriveFindByNameInput):
    exact: bool = Field(
        default=True, description="Whether to prioritize exact folder name matches first."
    )
    max_results: int = Field(
        default=10, ge=1, le=100, description="Maximum number of ranked matches to return."
    )


class DriveFindFileByNameInput(DriveFindByNameInput):
    file_type: str = Field(
        default="any",
        pattern="^(doc|sheet|pdf|folder|any)$",
        description="High-level file type filter mapped internally to Drive mime types.",
    )


class DriveSearchFilesAdvancedInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terms: list[str] = Field(
        min_length=1,
        max_length=8,
        description="Search terms used to build automatic Drive search strategies.",
    )
    mime_types: list[str] | None = Field(
        default=None, max_length=8, description="Optional Drive mime type filters."
    )
    match_mode: str = Field(
        default="all_terms",
        pattern="^(all_terms|any_term)$",
        description="Whether all terms or any term should be treated as required when ranking results.",
    )
    normalized: bool = Field(
        default=True,
        description="Whether to compare normalized names locally using lowercase, trimmed, accent-free text.",
    )
    fuzzy: bool = Field(
        default=True,
        description="Whether to use lightweight local fuzzy ranking on candidate names.",
    )
    include_trashed: bool = Field(
        default=False, description="Whether trashed files should be included."
    )
    parent_id: str | None = Field(default=None, description="Optional parent folder ID filter.")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Maximum number of ranked matches to return."
    )

    @model_validator(mode="after")
    def validate_terms(self) -> DriveSearchFilesAdvancedInput:
        cleaned_terms = [term.strip() for term in self.terms if term.strip()]
        if not cleaned_terms:
            raise ValueError("At least one non-empty search term is required")
        self.terms = list(dict.fromkeys(cleaned_terms))
        if self.mime_types is not None:
            self.mime_types = list(dict.fromkeys(self.mime_types))
        return self


class DriveGetFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str = Field(description="Drive file ID.")


class DriveDownloadFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str = Field(description="Drive file ID for binary download.")


class DriveExportFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str = Field(description="Drive file ID for a Google-native file export.")
    export_mime_type: str = Field(
        description="Target mime type for export, such as application/pdf."
    )


class DriveCreateFolderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    parent_id: str | None = None


class DriveCreateNativeFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    parent_id: str | None = None


class DrivePrepareWriteGoogleDocInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str = Field(description="Drive file ID for a native Google Doc.")
    content_text: str = Field(min_length=1, description="Text content to write into the document.")
    mode: str = Field(default="replace", pattern="^(replace|append)$")


class DrivePrepareWriteGoogleSheetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str = Field(description="Drive file ID for a native Google Sheet.")
    values: list[list[str | int | float | bool | None]] = Field(
        min_length=1,
        description="Tabular values to write into the spreadsheet.",
    )
    sheet_name: str | None = Field(default=None, description="Optional sheet/tab name.")
    create_sheet_if_missing: bool = Field(
        default=False,
        description="Whether to create the sheet/tab when `sheet_name` does not already exist.",
    )
    start_cell: str = Field(
        default="A1", description="Start cell in A1 notation for overwrite mode."
    )
    mode: str = Field(default="overwrite", pattern="^(overwrite|append)$")


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
    def validate_changes(self) -> DriveUpdateMetadataInput:
        if self.name is None and self.description is None:
            raise ValueError("At least one metadata field must be provided")
        return self


class DriveMoveFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    add_parent_id: str | None = None
    remove_parent_id: str | None = None

    @model_validator(mode="after")
    def validate_move(self) -> DriveMoveFileInput:
        if self.add_parent_id is None and self.remove_parent_id is None:
            raise ValueError("At least one parent change must be provided")
        return self


class DriveInlineContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_text: str | None = Field(
        default=None, description="Inline text content for UTF-8 files."
    )
    content_base64: str | None = Field(
        default=None, description="Base64 content for binary payloads."
    )
    mime_type: str = Field(description="Mime type for the uploaded or saved content.")

    @model_validator(mode="after")
    def validate_content(self) -> DriveInlineContentInput:
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

    file_id: str = Field(description="Drive file ID.")
    content: DriveInlineContentInput


class DrivePrepareDeleteFileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    permanent: bool = Field(
        default=False, description="Whether to permanently delete instead of moving to trash."
    )


class DrivePermissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(pattern="^(user|group|domain|anyone)$")
    role: str = Field(pattern="^(owner|organizer|fileOrganizer|writer|commenter|reader)$")
    email_address: str | None = None
    domain: str | None = None
    allow_file_discovery: bool | None = None

    @model_validator(mode="after")
    def validate_target(self) -> DrivePermissionInput:
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
