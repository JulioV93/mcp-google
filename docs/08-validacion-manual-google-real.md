# Validacion manual con Google real

> Configuración actual: [permisos persistentes](23-permisos-persistentes.md).
> En `server_policy`, habilitar `read_write` una vez y conservar el JWT; `permission_denied`
> requiere un cambio administrativo. Las instrucciones de `approved_tools`,
> `approval_required` y las variables antiguas de aprobación de esta guía describen
> exclusivamente el modo heredado `jwt_claims`. La confirmación de operaciones es técnica.

## Objetivo

Esta guia describe un flujo completo para validar manualmente el servidor MCP contra una cuenta Google real, usando credenciales OAuth verdaderas y un cliente MCP autenticado.

## Antes de empezar

Debes tener listo lo siguiente:

- `.env` completo con credenciales reales
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- un bearer token valido para el servidor MCP
- APIs habilitadas en Google Cloud Console:
  - Google Calendar API
  - Google Tasks API
  - Gmail API

## Variables recomendadas para esta prueba

```env
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
APP_BASE_URL=http://localhost:8000
DATABASE_URL=sqlite:///./data/dev.db
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
TOKEN_ENCRYPTION_KEY=<fernet-key>
GOOGLE_CLIENT_ID=<real-client-id>
GOOGLE_CLIENT_SECRET=<real-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/oauth/google/callback
GOOGLE_OAUTH_SCOPES=https://www.googleapis.com/auth/calendar,https://www.googleapis.com/auth/tasks,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.compose,https://www.googleapis.com/auth/gmail.modify,openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/userinfo.profile
GOOGLE_API_MAX_RETRIES=3
GOOGLE_API_RETRY_BASE_DELAY_SECONDS=1.0
GOOGLE_API_RETRY_MAX_DELAY_SECONDS=8.0
JWT_TEST_MODE=true
JWT_TEST_TOKEN=local-dev-token
JWT_TEST_SUBJECT=manual-test-user
REQUIRE_EXPLICIT_APPROVAL=false
```

## Paso 1: levantar el servidor

Con Python local:

```bash
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.main
```

O con Docker Compose:

```bash
docker compose run --rm mcp-google alembic upgrade head
docker compose up --build
```

Si cambias `.env` o cualquier setting de OAuth, reinicia el servidor antes de repetir la prueba.

## Paso 2: verificar salud y autenticacion basica

```bash
curl http://localhost:8000/health
```

Prueba MCP basica con el helper:

```bash
.venv/bin/python scripts/mcp_smoke_test.py --url http://localhost:8000/mcp --token local-dev-token
```

Debes ver el listado de tools disponibles.

Comprobaciones utiles adicionales:

Sin token debe fallar:

```bash
curl -i http://localhost:8000/oauth/google/status
```

Con token de prueba debe responder:

```bash
curl -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/status
```

## Paso 3: iniciar el flujo Google OAuth

```bash
curl -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/start
```

La respuesta devolvera un JSON con:

- `authorization_url`
- `state`
- `expires_at`
- `scopes`

Tambien puedes iniciar el flujo desde la tool MCP:

```bash
.venv/bin/python scripts/mcp_smoke_test.py --tool auth_google_begin
```

## Paso 4: completar consentimiento en navegador

1. copia `authorization_url`
2. abre la URL en el navegador
3. inicia sesion con la cuenta Google que quieres vincular
4. concede permisos
5. permite que Google redirija a `http://localhost:8000/oauth/google/callback`

## Paso 5: confirmar conexion activa

```bash
curl -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/status
```

Verificacion equivalente desde MCP:

```bash
.venv/bin/python scripts/mcp_smoke_test.py --tool auth_google_status
```

Respuesta esperada aproximada:

```json
{
  "connected": true,
  "google_email": "tu-cuenta@gmail.com",
  "scopes": ["..."],
  "status": "active"
}
```

## Paso 6: probar Calendar

Listar calendarios:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool calendar_list_calendars
```

Crear un evento:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool calendar_create_event \
  --args '{
    "calendar_id": "primary",
    "event": {
      "summary": "MCP Test Event",
      "start": {"dateTime": "2026-03-20T15:00:00Z"},
      "end": {"dateTime": "2026-03-20T15:30:00Z"}
    }
  }'
```

Crear un evento con color:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool calendar_create_event \
  --args '{
    "calendar_id": "primary",
    "event": {
      "summary": "MCP Test Event Color",
      "colorId": "5",
      "start": {"dateTime": "2026-03-20T15:00:00Z"},
      "end": {"dateTime": "2026-03-20T15:30:00Z"}
    }
  }'
```

Crear un evento recurrente diario con recordatorio personalizado 5 minutos antes:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool calendar_create_event \
  --args '{
    "calendar_id": "primary",
    "event": {
      "summary": "Rutina diaria MCP",
      "start": {"dateTime": "2026-03-20T08:00:00-03:00"},
      "end": {"dateTime": "2026-03-20T08:10:00-03:00"},
      "recurrence": ["RRULE:FREQ=DAILY"],
      "reminders": {
        "useDefault": false,
        "overrides": [
          {"method": "popup", "minutes": 5}
        ]
      }
    }
  }'
```

Anota el `event_id` que devuelve la creacion.

Listar eventos:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool calendar_list_events \
  --args '{
    "calendar_id": "primary",
    "query": "MCP Test Event"
  }'
```

Obtener el evento por ID:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool calendar_get_event \
  --args '{
    "calendar_id": "primary",
    "event_id": "<event_id>"
  }'
```

Actualizar el evento:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool calendar_update_event \
  --args '{
    "calendar_id": "primary",
    "event_id": "<event_id>",
    "event": {
      "summary": "MCP Test Event Updated",
      "start": {"dateTime": "2026-03-20T15:00:00Z"},
      "end": {"dateTime": "2026-03-20T16:00:00Z"}
    }
  }'
```

Actualizar el color del evento:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool calendar_update_event \
  --args '{
    "calendar_id": "primary",
    "event_id": "<event_id>",
    "event": {
      "summary": "MCP Test Event Updated",
      "colorId": "11",
      "start": {"dateTime": "2026-03-20T15:00:00Z"},
      "end": {"dateTime": "2026-03-20T16:00:00Z"}
    }
  }'
```

Actualizar un evento para dejarlo recurrente con recordatorio personalizado:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool calendar_update_event \
  --args '{
    "calendar_id": "primary",
    "event_id": "<event_id>",
    "event": {
      "summary": "Rutina diaria MCP actualizada",
      "start": {"dateTime": "2026-03-20T08:00:00-03:00"},
      "end": {"dateTime": "2026-03-20T08:10:00-03:00"},
      "recurrence": ["RRULE:FREQ=DAILY"],
      "reminders": {
        "useDefault": false,
        "overrides": [
          {"method": "popup", "minutes": 5}
        ]
      }
    }
  }'
```

En la respuesta o al consultar luego con `calendar_get_event`, verifica que aparezcan `color_id`, `recurrence` y `reminders` cuando corresponda.

Borrar el evento:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool calendar_delete_event \
  --args '{
    "calendar_id": "primary",
    "event_id": "<event_id>"
  }'
```

Anota el `operation_id` y confirma el borrado:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool calendar_confirm_delete_event \
  --args '{
    "operation_id": "<operation_id>"
  }'
```

## Paso 7: probar Tasks

Listar listas actuales:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_list_tasklists
```

Crear lista:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_create_tasklist \
  --args '{"title": "MCP Test List"}'
```

Anota el `tasklist_id` que devuelve la creacion.

Actualizar lista:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_update_tasklist \
  --args '{
    "tasklist_id": "<tasklist_id>",
    "title": "MCP Test List Updated"
  }'
```

Listar listas nuevamente:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_list_tasklists
```

Crear tarea:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_create_task \
  --args '{
    "tasklist_id": "<tasklist_id>",
    "task": {"title": "MCP Test Task", "notes": "Smoke test"}
  }'
```

Anota el `task_id` que devuelve la creacion.

Listar tareas:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_list_tasks \
  --args '{
    "tasklist_id": "<tasklist_id>"
  }'
```

Actualizar tarea:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_update_task \
  --args '{
    "tasklist_id": "<tasklist_id>",
    "task_id": "<task_id>",
    "task": {
      "title": "MCP Test Task Updated",
      "notes": "Smoke test updated"
    }
  }'
```

Completar tarea:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_complete_task \
  --args '{
    "tasklist_id": "<tasklist_id>",
    "task_id": "<task_id>"
  }'
```

Borrar tarea:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_delete_task \
  --args '{
    "tasklist_id": "<tasklist_id>",
    "task_id": "<task_id>"
  }'
```

Anota el `operation_id` y confirma:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_confirm_delete_task \
  --args '{
    "operation_id": "<operation_id>"
  }'
```

Borrar lista:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_delete_tasklist \
  --args '{
    "tasklist_id": "<tasklist_id>"
  }'
```

Anota el `operation_id` y confirma:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_confirm_delete_tasklist \
  --args '{
    "operation_id": "<operation_id>"
  }'
```

## Paso 8: probar Gmail

Listar mensajes:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool gmail_list_messages \
  --args '{
    "max_results": 5
  }'
```

Anota un `message_id` real de la respuesta si quieres probar lectura o borrado.

Obtener un mensaje:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool gmail_get_message \
  --args '{
    "message_id": "<message_id>"
  }'
```

Listar hilos:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool gmail_list_threads \
  --args '{
    "max_results": 5
  }'
```

Crear draft:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool gmail_create_draft \
  --args '{
    "message": {
      "to": ["tu-correo@example.com"],
      "subject": "Draft de prueba MCP",
      "body_text": "Mensaje de prueba"
    }
  }'
```

Anota el `draft_id` que devuelve la creacion.

Actualizar draft:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool gmail_update_draft \
  --args '{
    "draft_id": "<draft_id>",
    "message": {
      "to": ["tu-correo@example.com"],
      "subject": "Draft de prueba MCP actualizado",
      "body_text": "Mensaje de prueba actualizado"
    }
  }'
```

Borrar draft:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool gmail_delete_draft \
  --args '{
    "draft_id": "<draft_id>"
  }'
```

Enviar correo opcionalmente:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool gmail_send_email \
  --args '{
    "message": {
      "to": ["tu-correo@example.com"],
      "subject": "Envio real MCP",
      "body_text": "Mensaje enviado desde la prueba manual MCP"
    }
  }'
```

Anota el `operation_id` y confirma el envio:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool gmail_confirm_send_email \
  --args '{
    "operation_id": "<operation_id>"
  }'
```

Enviar un mensaje existente a la papelera opcionalmente:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool gmail_delete_message \
  --args '{
    "message_id": "<message_id>"
  }'
```

La tool `gmail_delete_message` en esta v1 mueve el mensaje a `TRASH`; no hace borrado permanente.

## Paso 9: validar tools sensibles con aprobacion explicita

Si activas:

```env
REQUIRE_EXPLICIT_APPROVAL=true
```

entonces las tools sensibles requeriran que el JWT incluya `approved_tools`.

Con `JWT_TEST_MODE=true`, el modo local no simula este claim automaticamente. Para validar este caso necesitas usar un JWT real emitido por tu plataforma o extender temporalmente el modo de prueba.

Tools sensibles iniciales:

- `gmail_send_email`
- `gmail_confirm_send_email`
- `gmail_delete_message`
- `calendar_delete_event`
- `calendar_confirm_delete_event`
- `tasks_delete_task`
- `tasks_confirm_delete_task`
- `tasks_delete_tasklist`
- `tasks_confirm_delete_tasklist`

## Paso 10: validar auditoria y rate limiting

- ejecuta varias llamadas repetidas a `/oauth/google/status` para comprobar `429`
- verifica que no aparezcan secretos en logs
- si usas Postgres o SQLite local, revisa la tabla `audit_logs`

### Validar manejo de errores Google y reintentos

Con la implementacion actual, el servidor diferencia mejor los errores del proveedor:

- `403 rateLimitExceeded` y `429 rateLimitExceeded` deben terminar como `rate_limited`
- `403 userRateLimitExceeded` y `403 quotaExceeded` tambien deben marcarse como errores recuperables
- `409 duplicate` debe salir como `provider_conflict`
- `412 conditionNotMet` debe salir como `provider_precondition_failed`

Durante una prueba real, si Google responde con limite de cuota o rate limit, espera:

- reintentos automaticos del cliente antes de fallar definitivamente
- logs con intentos de retry y razon del proveedor
- payload MCP final con `metadata.provider_reason`, `metadata.provider_status_code` y, si aplica, `metadata.retry_after_seconds`

Ejemplo de chequeo manual esperado para un throttle del proveedor:

```json
{
  "error": "rate_limited",
  "detail": "Rate Limit Exceeded",
  "retryable": true,
  "category": "rate_limit",
  "metadata": {
    "provider": "google",
    "provider_status_code": 403,
    "provider_reason": "rateLimitExceeded",
    "provider_domain": "usageLimits"
  }
}
```

Forzar rate limiting:

```bash
for i in $(seq 1 130); do
  curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/status
done
```

Revisar auditoria en SQLite:

```bash
sqlite3 data/dev.db "select id, tool_name, result_status, error_code, created_at from audit_logs order by id desc limit 20;"
```

Revisar estados OAuth en SQLite:

```bash
sqlite3 data/dev.db "select id, state, expires_at, created_at from oauth_states order by id desc limit 10;"
```

Revisar conexiones Google guardadas en SQLite:

```bash
sqlite3 data/dev.db "select id, google_email, status, expires_at, created_at from google_connections order by id desc limit 10;"
```

Si usas Postgres, cambia `sqlite3` por una consulta equivalente con `psql`.

## Criterios de exito

- el servidor levanta y responde `/health`
- el flujo OAuth completa el callback correctamente
- `auth_google_status` devuelve una conexion activa
- Calendar responde a create/list/delete
- Tasks responde a create/list/complete/delete
- Gmail responde a list/create_draft y, si decides, a send
- logs y auditoria no exponen tokens ni cuerpos sensibles

## Comandos utiles

Listar tools:

```bash
.venv/bin/python scripts/mcp_smoke_test.py
```

Llamar una tool puntual:

```bash
.venv/bin/python scripts/mcp_smoke_test.py --tool auth_google_status
```

Desconectar la cuenta Google actual:

```bash
.venv/bin/python scripts/mcp_smoke_test.py --tool auth_google_disconnect
```

O por HTTP:

```bash
curl -X POST -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/disconnect
```

## Notas practicas

- usa una cuenta Google de pruebas, no una personal critica
- prueba primero Calendar y Tasks antes que Gmail
- si Gmail devuelve permisos insuficientes, revisa scopes y consentimiento
- si el callback falla, revisa que `GOOGLE_REDIRECT_URI` coincida exactamente con la configurada en Google Cloud Console
