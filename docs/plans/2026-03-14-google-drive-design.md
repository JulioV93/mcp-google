# Google Drive integration design

## Objective

Add Google Drive support to the MCP server while preserving the current multi-user architecture, JWT identity model, Google OAuth flow, audit logging, and MCP tool registration pattern already used for Calendar, Tasks, and Gmail.

## Scope

The Drive integration should cover:

- file and folder listing
- metadata lookup
- search
- file download
- Google Workspace export
- folder and shortcut creation
- rename, move, and metadata updates
- upload
- content save/update for non-native files
- trash and permanent delete
- permissions and sharing

The following operations require double validation inside the MCP itself:

- upload
- save or content update
- delete or permanent delete
- share and permission changes

Out of scope for the first implementation:

- rich editing of native Google Docs, Sheets, or Slides through their dedicated APIs
- large streaming uploads/downloads
- background sync workflows

## Recommended architecture

Follow the existing domain pattern:

- `app/schemas/drive.py`
- `app/google/drive_client.py`
- `app/services/drive_service.py`
- `app/tools/drive_tools.py`

Reuse existing infrastructure:

- JWT auth middleware
- request context propagation
- Google OAuth token storage and refresh
- audit logging
- MCP tool registration

## Tool catalog

### Read tools

- `drive_list_files`
- `drive_search_files`
- `drive_get_file`
- `drive_list_permissions`
- `drive_download_file`
- `drive_export_file`

### Simple mutation tools

- `drive_create_folder`
- `drive_create_shortcut`
- `drive_update_metadata`
- `drive_move_file`

### Sensitive two-step tools

- `drive_prepare_upload`
- `drive_confirm_upload`
- `drive_prepare_save_file`
- `drive_confirm_save_file`
- `drive_prepare_delete_file`
- `drive_confirm_delete_file`
- `drive_prepare_share_file`
- `drive_confirm_share_file`
- `drive_prepare_revoke_permission`
- `drive_confirm_revoke_permission`

## Double validation flow

Sensitive operations use a `prepare` plus `confirm` pattern.

### Prepare step

The prepare tool:

- validates the requested operation
- normalizes the payload
- calculates a stable payload hash
- stores a pending operation tied to the authenticated user
- returns an `operation_id`, risk summary, and expiration timestamp

### Confirm step

The confirm tool:

- checks that the same authenticated user is confirming
- verifies the operation still exists and is pending
- verifies it has not expired
- verifies the normalized payload hash still matches
- executes the real Google Drive operation
- marks the pending operation as consumed

Recommended defaults:

- TTL: 10 minutes
- single-use operation ids
- trash by default for delete
- permanent delete only via an explicit permanent flag

## Data model additions

Add a table for pending confirmed operations, for example `pending_google_operations`, with fields such as:

- `id`
- `user_id`
- `provider`
- `operation_type`
- `resource_type`
- `resource_id`
- `resource_name`
- `payload_normalized`
- `payload_hash`
- `status`
- `expires_at`
- `confirmed_at`
- `created_at`
- `updated_at`

Recommended statuses:

- `pending`
- `confirmed`
- `expired`
- `cancelled`

## OAuth scopes

To support the full Drive feature set, add:

- `https://www.googleapis.com/auth/drive`

Impact:

- users who already granted consent will likely need to reconnect so the new Drive scope is granted

## File type rules

### Standard files

- support upload, download, and content update

### Folders

- support create, list, move, share, and delete semantics

### Google Docs, Sheets, Slides

- support metadata and export
- do not support native rich editing in v1 through Drive alone
- content save should reject unsupported native edit attempts with a typed error

### Shortcuts

- support create and metadata lookup

## Security and audit rules

- identity always comes from the validated JWT, never from tool arguments
- do not log raw content, base64 bodies, or secrets
- audit both the prepare and confirm phases of sensitive operations
- treat share and permission changes as sensitive operations

## Error model

Keep the current typed application error contract and extend it with Drive-specific cases such as:

- `google_drive_operation_confirmation_required`
- `google_drive_operation_not_found`
- `google_drive_operation_expired`
- `google_drive_operation_already_consumed`
- `google_drive_payload_mismatch`
- `google_drive_native_edit_not_supported`
- `google_drive_export_not_supported`
- `google_drive_content_too_large`

## Implementation phases

1. Add Drive scopes and auth-awareness.
2. Create Drive schemas, client, service, and MCP tools.
3. Implement read and navigation tools.
4. Implement simple metadata mutations.
5. Add persistence for pending confirmation operations.
6. Implement two-step upload/save/delete/share flows.
7. Add permissions management.
8. Harden limits, errors, and documentation.
9. Add and run tests.

## Success criteria

- Drive tools work for authenticated users with a connected Google account.
- Read operations execute directly.
- Sensitive operations cannot execute in a single step.
- Each sensitive operation produces both an intention record and an execution audit trail.
- Responses remain compact and agent-friendly.
