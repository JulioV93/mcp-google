# Guia de desarrollo local

## Objetivo

Esta guia explica como preparar el entorno local para trabajar en el servidor MCP, como levantar la app y como probar la base actual antes de continuar con mas funcionalidades.

## Requisitos previos

- Python 3.11 o superior
- Node.js si quieres usar MCP Inspector
- acceso a terminal dentro del proyecto

## Entorno virtual recomendado

Para este proyecto se recomienda usar un entorno virtual de Python desde el inicio. No es obligatorio, pero evita conflictos con dependencias globales y permite aislar versiones de `fastmcp`, `starlette`, `uvicorn`, `pydantic` y el resto del stack.

## Crear el entorno virtual

Desde la raiz del proyecto:

```bash
python3 -m venv .venv
```

## Activar el entorno virtual

En macOS o Linux:

```bash
source .venv/bin/activate
```

## Instalar dependencias

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Variables de entorno locales

Crea un archivo `.env` basado en `.env.example`.

```env
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
APP_BASE_URL=http://localhost:8000
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
ALLOWED_HOSTS=localhost,127.0.0.1,testserver
RATE_LIMIT_ENABLED=true
RATE_LIMIT_RPM=120
LOG_LEVEL=INFO
LOG_JSON=false
REQUIRE_EXPLICIT_APPROVAL=false
APPROVAL_REQUIRED_TOOLS=gmail_send_email,gmail_confirm_send_email,gmail_delete_message,calendar_delete_event,calendar_confirm_delete_event,tasks_delete_task,tasks_confirm_delete_task,tasks_delete_tasklist,tasks_confirm_delete_tasklist
MCP_SERVER_NAME=google-mcp-server
MCP_SERVER_VERSION=0.1.0
MCP_PATH=/mcp
JWT_ISSUER=http://localhost:8000/auth/dev
JWT_AUDIENCE=google-mcp-server
JWT_TEST_TOKEN=local-dev-token
JWT_TEST_MODE=true
JWT_TEST_SUBJECT=local-dev-user
GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS=10
GOOGLE_API_MAX_RETRIES=3
GOOGLE_API_RETRY_BASE_DELAY_SECONDS=1.0
GOOGLE_API_RETRY_MAX_DELAY_SECONDS=8.0
```

## Settings de retry para Google APIs

El servidor ahora incluye reintentos automaticos para errores temporales o de cuota devueltos por Google.

- `GOOGLE_API_MAX_RETRIES`: cantidad maxima de reintentos adicionales por request
- `GOOGLE_API_RETRY_BASE_DELAY_SECONDS`: base del backoff exponencial
- `GOOGLE_API_RETRY_MAX_DELAY_SECONDS`: techo del backoff truncado

Notas utiles:

- si Google devuelve `Retry-After`, ese valor se respeta antes que el backoff calculado
- `403 rateLimitExceeded` y `429 rateLimitExceeded` se tratan como errores recuperables
- `quotaExceeded` y `userRateLimitExceeded` tambien se clasifican como `rate_limited`
- `backendError` y otros `5xx` se reintentan automaticamente hasta agotar el limite configurado

## Levantar el servidor

Opcion 1:

```bash
python -m app.main
```

Opcion 2:

```bash
mcp-google-server
```

## Levantar Postgres local con Docker Compose

Si quieres probar el flujo con una base mas cercana a produccion:

```bash
docker compose up --build
```

En ese caso, el servicio `mcp-google` usara Postgres en lugar del SQLite local definido en `.env`.

## Aplicar migraciones localmente

Antes de probar el flujo OAuth o los servicios Google, aplica la base de datos:

```bash
alembic upgrade head
```

## Probar el healthcheck

```bash
curl http://localhost:8000/health
```

Respuesta esperada aproximada:

```json
{
  "status": "ok",
  "service": "google-mcp-server",
  "version": "0.1.0",
  "environment": "development",
  "mcp_path": "/mcp"
}
```

## Probar autenticacion local de desarrollo

Mientras se construye la integracion real de JWT, el proyecto puede usar `JWT_TEST_MODE=true` para aceptar un token de desarrollo fijo.

Header esperado:

```text
Authorization: Bearer local-dev-token
```

Si activas aprobaciones explicitas, el JWT real de tu plataforma debe incluir `approved_tools` con las tools sensibles autorizadas para esa ejecucion.

## Probar el MCP server con cliente Python

```python
import asyncio
from fastmcp import Client


async def main():
    headers = {"Authorization": "Bearer local-dev-token"}
    async with Client("http://localhost:8000/mcp", headers=headers) as client:
        tools = await client.list_tools()
        print([tool.name for tool in tools])

        result = await client.call_tool("ping", {})
        print(result)


asyncio.run(main())
```

## Probar el flujo Google OAuth localmente

Una vez configurados `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `GOOGLE_REDIRECT_URI` en `.env`:

```bash
curl -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/start
```

La respuesta devolvera una `authorization_url`. Abrela en el navegador y completa el consentimiento. Luego valida el estado:

```bash
curl -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/status
```

Si la vinculacion fue correcta, deberias ver `connected: true`.

## Probar con MCP Inspector

MCP Inspector es util para probar el endpoint MCP de forma interactiva desde el navegador, sin escribir codigo Python adicional. Te permite:

- conectar manualmente al endpoint MCP remoto
- listar tools disponibles
- ejecutar tools una por una
- ver el schema de entrada de cada tool
- inspeccionar respuestas y errores HTTP

### Cuando usarlo

Usalo despues de confirmar que:

- el servidor ya esta levantado en `http://localhost:8000`
- `/health` responde correctamente
- tienes un token valido, por ejemplo `local-dev-token`

### Paso 1: arrancar MCP Inspector

Desde otra terminal, en la raiz del proyecto o en cualquier carpeta:

```bash
npx @modelcontextprotocol/inspector
```

Normalmente veras en terminal una URL local del inspector. Suele ser algo parecido a una de estas:

- `http://localhost:6274`
- `http://127.0.0.1:6274`

Abre esa URL en tu navegador.

### Paso 2: preparar la conexion

Dentro del Inspector, crea una conexion nueva o usa el formulario inicial de conexion.

Completa estos valores:

- transport: `streamable-http`
- server URL: `http://localhost:8000/mcp`
- method o connection type: `remote` o `http`, segun como aparezca en la UI

En headers agrega exactamente:

```text
Authorization: Bearer local-dev-token
```

Si el Inspector permite agregar multiples headers, puedes dejar solo ese para la primera prueba.

### Paso 3: conectar

Pulsa el boton equivalente a:

- `Connect`
- `Start session`
- `Connect to server`

el nombre exacto puede cambiar segun la version del Inspector.

Si la conexion funciona, deberias ver:

- la sesion marcada como conectada
- la lista de tools del servidor
- los metadatos basicos del servidor MCP

Si tu cliente envia header `Origin`, debe coincidir con alguno de `ALLOWED_ORIGINS`.

### Paso 4: primeras pruebas recomendadas

Empieza por las tools mas simples.

#### 4.1 Listar tools

Busca una accion como:

- `List Tools`
- `Tools`
- `Refresh tools`

Deberias ver tools como:

- `auth_google_begin`
- `auth_google_status`
- `calendar_list_calendars`
- `tasks_list_tasklists`
- `gmail_list_messages`

#### 4.2 Ver el schema de una tool

Haz clic sobre una tool, por ejemplo `auth_google_status`.

El Inspector deberia mostrar:

- nombre de la tool
- descripcion
- parametros esperados
- schema JSON de entrada

Esto sirve para saber exactamente que payload mandar cuando una tool necesita argumentos.

#### 4.3 Ejecutar una tool sin argumentos

Prueba primero:

- `auth_google_status`

Como no necesita argumentos, ejecutala con `{}` o sin body, dependiendo de la UI.

Resultado esperado antes de vincular Google:

```json
{
  "connected": false,
  "google_email": null,
  "scopes": [],
  "status": null
}
```

#### 4.4 Ejecutar una tool con argumentos

Despues de vincular Google, prueba por ejemplo `calendar_list_events` con este payload:

```json
{
  "calendar_id": "primary",
  "max_results": 10
}
```

O `tasks_create_tasklist` con este payload:

```json
{
  "title": "Lista creada desde Inspector"
}
```

O `gmail_list_messages` con este payload:

```json
{
  "max_results": 5
}
```

### Paso 5: orden sugerido de pruebas dentro del Inspector

Una vez conectado, este es el mejor orden para validar el sistema:

1. `auth_google_status`
2. `auth_google_begin`
3. completar OAuth en navegador
4. `auth_google_status` otra vez
5. `calendar_list_calendars`
6. `tasks_list_tasklists`
7. `gmail_list_messages`

Si esas funcionan, continua con create/update/delete en cada servicio.

### Como usarlo junto con el navegador en el flujo OAuth

Puedes iniciar el flujo OAuth desde Inspector asi:

1. ejecuta `auth_google_begin`
2. copia `authorization_url` de la respuesta
3. abre esa URL en el navegador
4. completa consentimiento Google
5. vuelve al Inspector
6. ejecuta `auth_google_status`

Si la vinculacion salio bien, ahora deberias ver `connected: true`.

### Acciones sugeridas despues de conectar

- ejecutar `auth_google_status`
- ejecutar `auth_google_begin`
- ejecutar `calendar_list_calendars`
- ejecutar `tasks_list_tasklists`
- ejecutar `gmail_list_messages`

### Ejemplos de payloads utiles para copiar y pegar

`calendar_create_event`:

```json
{
  "calendar_id": "primary",
  "event": {
    "summary": "Evento desde Inspector",
    "colorId": "5",
    "start": {"dateTime": "2026-03-20T15:00:00Z"},
    "end": {"dateTime": "2026-03-20T15:30:00Z"}
  }
}
```

`calendar_create_event` con recurrencia diaria y recordatorio 5 minutos antes:

```json
{
  "calendar_id": "primary",
  "event": {
    "summary": "Rutina diaria desde Inspector",
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
}
```

`calendar_update_event` para cambiar duracion y color del evento:

```json
{
  "calendar_id": "primary",
  "event_id": "<event_id>",
  "event": {
    "summary": "Evento desde Inspector actualizado",
    "colorId": "11",
    "start": {"dateTime": "2026-03-20T15:00:00Z"},
    "end": {"dateTime": "2026-03-20T16:00:00Z"}
  }
}
```

`tasks_create_task`:

```json
{
  "tasklist_id": "<tasklist_id>",
  "task": {
    "title": "Tarea desde Inspector",
    "notes": "Prueba manual local"
  }
}
```

`gmail_create_draft`:

```json
{
  "message": {
    "to": ["tu-correo@example.com"],
    "subject": "Draft desde Inspector",
    "body_text": "Mensaje de prueba manual"
  }
}
```

`gmail_delete_message` mueve el mensaje a la papelera, no lo borra definitivamente. Payload:

```json
{
  "message_id": "<message_id>"
}
```

### Problemas comunes con MCP Inspector

#### El Inspector no abre en el navegador

- revisa la URL que imprimio `npx @modelcontextprotocol/inspector`
- si no abre automaticamente, copiala manualmente
- confirma que Node.js este instalado

#### El Inspector conecta pero no lista tools

- confirma que el servidor MCP siga levantado
- prueba `curl http://localhost:8000/health`
- verifica que la URL usada sea `http://localhost:8000/mcp`

#### Recibo `401 unauthorized_client`

- revisa el header `Authorization`
- usa exactamente `Bearer local-dev-token` si estas en `JWT_TEST_MODE=true`

#### Recibo `403 origin_not_allowed`

- agrega a `ALLOWED_ORIGINS` el origen real desde el que sirve el Inspector
- por ejemplo, si Inspector abre en `http://localhost:6274`, agregalo al `.env`
- reinicia el servidor despues del cambio

Ejemplo:

```env
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://localhost:6274
```

#### Una tool da error de Google aunque la conexion MCP funciona

- ejecuta `auth_google_status`
- confirma que `connected` sea `true`
- si sigue en `false`, completa primero el flujo OAuth
- si la tool requiere permisos, revisa los scopes concedidos

### Resumen operativo

Para una prueba local completa con Inspector:

1. levanta el servidor
2. abre MCP Inspector con `npx @modelcontextprotocol/inspector`
3. conecta a `http://localhost:8000/mcp`
4. agrega `Authorization: Bearer local-dev-token`
5. ejecuta `auth_google_begin`
6. completa OAuth en el navegador
7. vuelve y ejecuta `auth_google_status`
8. prueba Calendar, Tasks y Gmail desde la UI

## Pruebas HTTP rapidas

Sin token, el endpoint MCP debe rechazar la llamada.

Con token de desarrollo, el endpoint MCP debe aceptar la conexion.

Ejemplo de request autenticado al healthcheck no es necesario, porque `health` queda publico.

## Problemas comunes

### El editor marca imports como faltantes

Normalmente significa que el editor no esta apuntando al interprete de `.venv`.

### `fastmcp` o `pydantic_settings` no existen

Significa que no se han instalado las dependencias dentro del entorno virtual activo.

### El puerto 8000 esta ocupado

Puedes cambiar `APP_PORT` en tu `.env`.

### El cliente MCP no autentica

Verifica que este enviando el header:

```text
Authorization: Bearer local-dev-token
```

### El endpoint MCP responde `403 origin_not_allowed`

Agrega el origen correcto a `ALLOWED_ORIGINS` en `.env`.

### Una tool sensible responde que requiere aprobacion

Si `REQUIRE_EXPLICIT_APPROVAL=true`, tu plataforma debe emitir un JWT con `approved_tools` incluyendo la tool requerida.

## Flujo recomendado de trabajo local

1. activar `.venv`
2. instalar dependencias
3. levantar el servidor
4. probar `/health`
5. abrir MCP Inspector y conectar a `http://localhost:8000/mcp`
6. ejecutar `auth_google_status`
7. si aplica, ejecutar `auth_google_begin` y completar OAuth en el navegador
8. probar Calendar, Tasks y Gmail desde Inspector o desde `scripts/mcp_smoke_test.py`
