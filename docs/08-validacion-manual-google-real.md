# Validacion manual con Google real

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
JWT_TEST_MODE=true
JWT_TEST_TOKEN=local-dev-token
JWT_TEST_SUBJECT=manual-test-user
```

## Paso 1: levantar el servidor

Con Python local:

```bash
source .venv/bin/activate
alembic upgrade head
python -m app.main
```

O con Docker Compose:

```bash
docker compose up --build
docker compose run --rm mcp-google alembic upgrade head
```

## Paso 2: verificar salud y autenticacion basica

```bash
curl http://localhost:8000/health
```

Prueba MCP basica con el helper:

```bash
.venv/bin/python scripts/mcp_smoke_test.py --url http://localhost:8000/mcp --token local-dev-token
```

Debes ver el listado de tools disponibles.

## Paso 3: iniciar el flujo Google OAuth

```bash
curl -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/start
```

La respuesta devolvera un JSON con:

- `authorization_url`
- `state`
- `expires_at`
- `scopes`

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

Verifica luego con `calendar_list_events` y borra con `calendar_delete_event`.

## Paso 7: probar Tasks

Crear lista:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_create_tasklist \
  --args '{"title": "MCP Test List"}'
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

Completa con `tasks_complete_task` y borra con `tasks_delete_task`.

## Paso 8: probar Gmail

Listar mensajes:

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool gmail_list_messages
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

Opcionalmente, enviar correo con `gmail_send_email`.

## Paso 9: validar tools sensibles con aprobacion explicita

Si activas:

```env
REQUIRE_EXPLICIT_APPROVAL=true
```

entonces las tools sensibles requeriran que el JWT incluya `approved_tools`.

Con `JWT_TEST_MODE=true`, el modo local no simula este claim automaticamente. Para validar este caso necesitas usar un JWT real emitido por tu plataforma o extender temporalmente el modo de prueba.

Tools sensibles iniciales:

- `gmail_send_email`
- `gmail_delete_message`
- `calendar_delete_event`
- `tasks_delete_task`
- `tasks_delete_tasklist`

## Paso 10: validar auditoria y rate limiting

- ejecuta varias llamadas repetidas a `/oauth/google/status` para comprobar `429`
- verifica que no aparezcan secretos en logs
- si usas Postgres o SQLite local, revisa la tabla `audit_logs`

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

## Notas practicas

- usa una cuenta Google de pruebas, no una personal critica
- prueba primero Calendar y Tasks antes que Gmail
- si Gmail devuelve permisos insuficientes, revisa scopes y consentimiento
- si el callback falla, revisa que `GOOGLE_REDIRECT_URI` coincida exactamente con la configurada en Google Cloud Console
