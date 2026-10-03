# Modelo de datos y tools MCP

> Configuración actual: [permisos persistentes](23-permisos-persistentes.md).
> En `server_policy`, habilitar `read_write` una vez y conservar el JWT; `permission_denied`
> requiere un cambio administrativo. Las instrucciones de `approved_tools`,
> `approval_required` y las variables antiguas de aprobación de esta guía describen
> exclusivamente el modo heredado `jwt_claims`. La confirmación de operaciones es técnica.

## Modelo de datos

### Tabla `users`

- `id`
- `external_subject`
- `tenant_id` nullable
- `created_at`
- `updated_at`

### Tabla `google_connections`

- `id`
- `user_id` unico
- `google_email`
- `google_subject`
- `status`
- `granted_scopes`
- `access_token_encrypted`
- `refresh_token_encrypted`
- `expires_at`
- `created_at`
- `updated_at`

### Tabla `oauth_states`

- `id`
- `user_id`
- `provider`
- `state`
- `code_verifier`
- `requested_scopes`
- `expires_at`

### Tabla `audit_logs`

- `id`
- `user_id`
- `tool_name`
- `provider`
- `resource_type`
- `arguments_redacted`
- `result_status`
- `error_code`
- `created_at`

## Contexto multiusuario

- Cada usuario tiene una sola cuenta Google conectada en v1.
- El `user_id` de trabajo interno se resuelve desde `external_subject` del JWT.
- Las tools nunca eligen manualmente la cuenta Google a usar.

## Tools MCP de autenticacion

### `auth_google_begin`

- inicia el flujo OAuth Google
- devuelve URL de consentimiento
- requiere usuario autenticado

### `auth_google_status`

- informa si existe conexion activa
- devuelve email Google conectado y scopes concedidos

### `auth_google_disconnect`

- revoca o invalida la conexion del usuario
- elimina o marca la conexion como desconectada

## Tools MCP de Google Calendar

### `calendar_list_calendars`

- lista calendarios disponibles del usuario

### `calendar_list_events`

- lista eventos por calendario
- soporta rango de fechas y paginacion

### `calendar_get_event`

- obtiene un evento puntual por `calendar_id` y `event_id`

### `calendar_create_event`

- crea un evento
- valida horarios, timezone y estructura minima
- soporta `colorId` para asignar color al evento al crearlo
- soporta `recurrence` en formato RRULE de Google Calendar
- soporta `reminders.useDefault` y `reminders.overrides`

### `calendar_update_event`

- actualiza un evento existente
- preferible con semantica de patch en v1
- permite actualizar `colorId` del evento
- permite actualizar recurrencia y recordatorios personalizados

### `calendar_delete_event`

- prepara el borrado de un evento
- devuelve `operation_id` y preview para confirmacion
- no elimina inmediatamente

### `calendar_confirm_delete_event`

- confirma el borrado de un evento preparado
- operacion sensible y auditada

## Tools MCP de Google Tasks

### Tasklists

- `tasks_list_tasklists`
- `tasks_create_tasklist`
- `tasks_update_tasklist`
- `tasks_delete_tasklist`
- `tasks_confirm_delete_tasklist`

### Tasks

- `tasks_list_tasks`
- `tasks_create_task`
- `tasks_update_task`
- `tasks_complete_task`
- `tasks_delete_task`
- `tasks_confirm_delete_task`

## Tools MCP de Gmail

### Lectura

- `gmail_list_messages`
- `gmail_get_message`
- `gmail_list_threads`

### Drafts

- `gmail_create_draft`
- `gmail_update_draft`
- `gmail_delete_draft`

### Acciones de salida

- `gmail_send_email`
- `gmail_confirm_send_email`
- `gmail_delete_message`

## Tools MCP de Google Drive

### Lectura

- `drive_list_files`
- `drive_search_files`
- `drive_get_file`
- `drive_list_permissions`
- `drive_download_file`
- `drive_export_file`

### Mutacion simple

- `drive_create_folder`
- `drive_create_google_doc`
- `drive_create_google_sheet`
- `drive_create_google_slide`
- `drive_create_shortcut`
- `drive_update_metadata`
- `drive_move_file`

### Mutacion sensible con doble validacion

- `calendar_delete_event`
- `calendar_confirm_delete_event`
- `tasks_delete_task`
- `tasks_confirm_delete_task`
- `tasks_delete_tasklist`
- `tasks_confirm_delete_tasklist`
- `gmail_send_email`
- `gmail_confirm_send_email`
- `drive_prepare_upload`
- `drive_prepare_upload_markdown`
- `drive_confirm_upload`
- `drive_prepare_save_file`
- `drive_confirm_save_file`
- `drive_prepare_write_google_doc`
- `drive_confirm_write_google_doc`
- `drive_prepare_write_google_sheet`
- `drive_confirm_write_google_sheet`
- `drive_prepare_delete_file`
- `drive_confirm_delete_file`
- `drive_prepare_share_file`
- `drive_confirm_share_file`
- `drive_prepare_revoke_permission`
- `drive_confirm_revoke_permission`

## Notas de modelado Gmail

- Gmail no debe tratarse como CRUD puro sobre mensajes ya existentes.
- En v1, la entidad editable principal es el draft.
- El envio se trata como accion separada con flujo prepare/confirm.
- `gmail_delete_message` en v1 envia el mensaje a la papelera; no realiza borrado permanente.
- El borrado debe auditarse de forma reforzada.

## Normalizacion de respuestas

Las respuestas deben ser pequenas, consistentes y legibles por un agente:

- ids
- estado
- resumen o snippet corto
- links cuando existan
- `next_page_token` cuando aplique
- `resource_identity`
- `human_summary`
- `next_suggested_actions`
- `safety_level`

## Campos recomendados en respuestas

### Calendar

- `id`
- `calendar_id`
- `summary`
- `start`
- `end`
- `html_link`

### Tasks

- `id`
- `tasklist_id`
- `title`
- `status`
- `due`
- `updated`

### Gmail

- `id`
- `thread_id`
- `subject`
- `from`
- `to`
- `snippet`
- `label_ids`

## Reglas de salida

- no devolver payloads enormes por defecto
- no devolver cuerpos completos de correo salvo que la tool lo requiera claramente
- mantener formato de error estable

## Contrato de errores Google

- Todas las integraciones Google comparten un mapeo centralizado en `app/google/errors.py`.
- La clasificacion ya no depende solo del status HTTP; prioriza `error.errors[].reason` devuelto por Google.
- Las tools siguen devolviendo un contrato MCP estable con `error`, `detail`, `retryable`, `category` y `metadata` cuando aplique.

### Razones Google tratadas de forma explicita

- `rateLimitExceeded`, `userRateLimitExceeded`, `quotaExceeded`, `dailyLimitExceeded` -> `rate_limited`
- `backendError` y errores `5xx` -> `provider_temporary_error`
- `insufficientPermissions`, `forbidden`, `forbiddenForNonOrganizer` -> `insufficient_scope`
- `authError` o `401` -> `google_consent_required`
- `notFound` o `404` -> `resource_not_found`
- `duplicate`, `conflict` o `409` -> `provider_conflict`
- `conditionNotMet` o `412` -> `provider_precondition_failed`

### Metadata relevante de proveedor

- `provider`: proveedor origen, por ejemplo `google`
- `provider_status_code`: status HTTP original devuelto por Google
- `provider_error_code`: codigo incluido dentro del payload JSON de Google
- `provider_reason`: razon oficial de Google usada para clasificar el error
- `provider_domain`: dominio del error, por ejemplo `usageLimits` o `global`
- `provider_message`: mensaje legible devuelto por Google
- `retry_after_seconds`: valor de `Retry-After` si Google lo envia

### Politica de retry

- Las llamadas Google usan un helper comun de ejecucion para `Calendar`, `Gmail`, `Drive` y `Tasks`.
- Si el error es `retryable`, el cliente aplica truncated exponential backoff con jitter.
- Si Google devuelve `Retry-After`, ese valor tiene prioridad sobre el backoff calculado.
- Si se agota el presupuesto de reintentos, se propaga el ultimo error ya clasificado al contrato MCP.
