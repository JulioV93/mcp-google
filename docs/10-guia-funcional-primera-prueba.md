# Guia funcional para la primera prueba real

## Objetivo

Esta guia esta pensada para hacer tu primera prueba funcional real de punta a punta, sin asumir contexto adicional. Sigue los pasos en orden y marca cada checklist.

## Checklist inicial rapido

- [ ] Ya complete `docs/09-checklist-prerrequisitos-prueba-real.md`
- [ ] Tengo `.env` listo
- [ ] Tengo credenciales Google reales
- [ ] Tengo una cuenta Google de prueba

## Paso 1: preparar el entorno

### Opcion Python local

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### Opcion con Docker Compose

```bash
docker compose up --build
```

### Checklist del paso 1

- [x ] El entorno virtual existe o Docker Compose levanta correctamente.
- [x ] Las dependencias quedaron instaladas.

## Paso 2: revisar `.env`

Confirma como minimo:

```env
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
APP_BASE_URL=http://localhost:8000
DATABASE_URL=sqlite:///./data/dev.db
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
TOKEN_ENCRYPTION_KEY=<fernet-key>
GOOGLE_CLIENT_ID=<client-id>
GOOGLE_CLIENT_SECRET=<client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/oauth/google/callback
JWT_TEST_MODE=true
JWT_TEST_TOKEN=local-dev-token
JWT_TEST_SUBJECT=manual-test-user
REQUIRE_EXPLICIT_APPROVAL=false
```

### Checklist del paso 2

- [x ] `GOOGLE_CLIENT_ID` esta completo.
- [x ] `GOOGLE_CLIENT_SECRET` esta completo.
- [x ] `GOOGLE_REDIRECT_URI` coincide exactamente con Google Cloud Console.
- [ ] `TOKEN_ENCRYPTION_KEY` esta definido.

## Paso 3: aplicar migraciones

### Local

```bash
alembic upgrade head
```

### Con Compose

```bash
docker compose run --rm mcp-google alembic upgrade head
```

### Checklist del paso 3

- [ ] Las migraciones corrieron sin errores.

## Paso 4: levantar el servidor

### Local

```bash
python -m app.main
```

### Con Compose

```bash
docker compose up --build
```

### Checklist del paso 4

- [ ] El servidor quedo levantado.
- [ ] No hay errores de configuracion al iniciar.

## Paso 5: probar salud basica

```bash
curl http://localhost:8000/health
```

Debes ver `status: ok`.

### Checklist del paso 5

- [ ] `/health` responde `200`.

## Paso 6: validar acceso MCP autenticado

```bash
.venv/bin/python scripts/mcp_smoke_test.py --url http://localhost:8000/mcp --token local-dev-token
```

Debes ver la lista de tools.

### Checklist del paso 6

- [ ] El smoke test lista tools MCP.
- [ ] No recibo `401`.
- [ ] No recibo `403 origin_not_allowed`.

## Paso 7: iniciar Google OAuth

```bash
curl -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/start
```

Copia el valor de `authorization_url`.

### Checklist del paso 7

- [ ] Recibi `authorization_url`.
- [ ] Recibi `state`.

## Paso 8: completar consentimiento

1. abre `authorization_url` en el navegador
2. inicia sesion con la cuenta Google de prueba
3. acepta los permisos
4. deja que Google redirija a `/oauth/google/callback`

### Checklist del paso 8

- [ ] Google muestra la pantalla de consentimiento.
- [ ] El callback del servidor responde sin error.

## Paso 9: confirmar vinculacion

```bash
curl -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/status
```

Debes ver `connected: true`.

### Checklist del paso 9

- [ ] `connected` es `true`.
- [ ] `google_email` corresponde a la cuenta esperada.

## Paso 10: probar Calendar

### Listar calendarios

```bash
.venv/bin/python scripts/mcp_smoke_test.py --tool calendar_list_calendars
```

### Crear evento

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool calendar_create_event \
  --args '{
    "calendar_id": "primary",
    "event": {
      "summary": "Primera prueba MCP",
      "start": {"dateTime": "2026-03-20T15:00:00Z"},
      "end": {"dateTime": "2026-03-20T15:30:00Z"}
    }
  }'
```

Si quieres probar colores desde el inicio, puedes agregar `"colorId": "5"` dentro de `event`.

### Checklist del paso 10

- [ ] Puedo listar calendarios.
- [ ] Puedo crear un evento.
- [ ] Puedo ver el evento con `calendar_list_events`.

## Paso 11: probar Tasks

### Crear tasklist

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_create_tasklist \
  --args '{"title": "Lista de prueba MCP"}'
```

### Crear task

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool tasks_create_task \
  --args '{
    "tasklist_id": "<tasklist_id>",
    "task": {"title": "Tarea de prueba", "notes": "Smoke test"}
  }'
```

### Checklist del paso 11

- [ ] Puedo crear una lista.
- [ ] Puedo crear una tarea.
- [ ] Puedo completar una tarea.

## Paso 12: probar Gmail

### Listar mensajes

```bash
.venv/bin/python scripts/mcp_smoke_test.py --tool gmail_list_messages
```

### Crear draft

```bash
.venv/bin/python scripts/mcp_smoke_test.py \
  --tool gmail_create_draft \
  --args '{
    "message": {
      "to": ["tu-correo@example.com"],
      "subject": "Prueba draft MCP",
      "body_text": "Mensaje funcional de prueba"
    }
  }'
```

### Checklist del paso 12

- [ ] Puedo listar mensajes.
- [ ] Puedo crear un draft.
- [ ] Opcional: puedo preparar y confirmar el envio de un correo.

## Paso 13: probar borrado y operaciones sensibles

Haz esto solo si ya validaste lo anterior.

### Calendar: borrar con confirmacion

1. Ejecuta `calendar_delete_event`
2. Copia el `operation_id`
3. Ejecuta `calendar_confirm_delete_event` con ese `operation_id`

### Tasks: borrar con confirmacion

1. Ejecuta `tasks_delete_task` o `tasks_delete_tasklist`
2. Copia el `operation_id`
3. Ejecuta `tasks_confirm_delete_task` o `tasks_confirm_delete_tasklist`

### Gmail: enviar con confirmacion

1. Ejecuta `gmail_send_email`
2. Revisa el preview devuelto
3. Ejecuta `gmail_confirm_send_email` con el `operation_id`

### Checklist del paso 13

- [ ] Ya decidi si usare aprobacion explicita.
- [ ] No estoy trabajando sobre datos criticos.
- [ ] Entiendo que las operaciones sensibles usan prepare/confirm.

## Paso 14: revisar auditoria y limites

Valida que:

- los logs no expongan tokens
- los cuerpos sensibles se redacten
- `audit_logs` reciba entradas
- el rate limiting responda con `429` si fuerzas suficientes requests

### Checklist del paso 14

- [ ] Los logs no exponen secretos.
- [ ] Existe trazabilidad de acciones.
- [ ] El rate limiting funciona.

## Criterio de prueba exitosa

La primera prueba real es exitosa cuando:

- [ ] OAuth Google funciona
- [ ] `auth_google_status` devuelve conexion activa
- [ ] Calendar responde bien
- [ ] Tasks responde bien
- [ ] Gmail responde bien
- [ ] no aparecen secretos en logs

## Problemas comunes

### `provider_error` al iniciar OAuth

- revisa `GOOGLE_CLIENT_ID`
- revisa `GOOGLE_CLIENT_SECRET`
- revisa APIs habilitadas

### Error en callback

- revisa `GOOGLE_REDIRECT_URI`
- revisa redirect URI registrada en Google Cloud Console

### `403 origin_not_allowed`

- agrega el origen correcto a `ALLOWED_ORIGINS`

### `approval_required`

- desactiva temporalmente `REQUIRE_EXPLICIT_APPROVAL`
- o usa un JWT real con `approved_tools`
