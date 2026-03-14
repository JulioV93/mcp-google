# Guia para conectar este MCP a OpenCode

## Objetivo

Esta guia explica paso a paso como conectar este servidor MCP remoto a OpenCode para que el agente pueda descubrir y ejecutar tools de Calendar, Tasks, Gmail y autenticacion Google.

## Que vas a conectar exactamente

Este proyecto expone un servidor MCP remoto por HTTP usando transporte `streamable-http`.

Datos base en local:

- MCP URL: `http://localhost:8000/mcp`
- Healthcheck: `http://localhost:8000/health`
- Auth del cliente: `Authorization: Bearer <token>`

En entorno local de desarrollo, el token por defecto es:

```text
local-dev-token
```

## Requisitos previos

Antes de intentar la conexion desde OpenCode, confirma lo siguiente:

- Python y dependencias del proyecto instaladas
- `.env` configurado
- base de datos preparada con migraciones
- servidor MCP levantado en local
- `JWT_TEST_MODE=true` si estas haciendo una prueba local rapida
- `JWT_TEST_TOKEN=local-dev-token`

## Paso 1: levantar el servidor MCP

Desde la raiz del proyecto:

```bash
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.main
```

Si usas Docker Compose:

```bash
docker compose run --rm mcp-google alembic upgrade head
docker compose up --build
```

## Paso 2: verificar que el servidor responde

Prueba el healthcheck:

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

Si esto falla, no intentes conectar OpenCode todavia.

## Paso 3: verificar el MCP antes de usar OpenCode

Antes de configurar OpenCode, valida el endpoint MCP con una herramienta manual.

La forma recomendada es MCP Inspector:

```bash
npx @modelcontextprotocol/inspector
```

Luego conecta con:

- transport: `streamable-http`
- server URL: `http://localhost:8000/mcp`
- header: `Authorization: Bearer local-dev-token`

Si Inspector lista las tools, el servidor ya esta listo para ser consumido por OpenCode.

## Paso 4: datos que OpenCode necesita

OpenCode debe registrar este proyecto como un servidor MCP remoto.

Los datos importantes son estos:

- nombre del servidor: `google-mcp` o el nombre que prefieras
- transporte: `streamable-http`
- URL: `http://localhost:8000/mcp`
- header `Authorization: Bearer local-dev-token`

Configuracion conceptual:

```json
{
  "name": "google-mcp",
  "transport": "streamable-http",
  "url": "http://localhost:8000/mcp",
  "headers": {
    "Authorization": "Bearer local-dev-token"
  }
}
```

El nombre exacto de los campos puede variar segun la version o el formato de configuracion de OpenCode, pero el contenido necesario es ese.

## Paso 5: configurar el servidor MCP en OpenCode

En OpenCode debes crear una entrada de servidor MCP remoto con estos valores:

1. nombre: `google-mcp`
2. tipo o transporte: `streamable-http`
3. URL del servidor: `http://localhost:8000/mcp`
4. header de autenticacion: `Authorization: Bearer local-dev-token`

Si OpenCode distingue entre MCP local y MCP remoto, debes elegir MCP remoto por HTTP, no un comando local.

## Paso 6: validar la conexion desde OpenCode

Una vez guardada la configuracion, OpenCode deberia poder:

- conectar con el servidor MCP
- listar tools disponibles
- invocar tools sin error de autenticacion

Las primeras tools recomendadas para probar son:

- `auth_google_status`
- `auth_google_begin`
- `calendar_list_calendars`
- `tasks_list_tasklists`
- `gmail_list_messages`

## Paso 7: conectar la cuenta Google del usuario

Que OpenCode vea las tools no significa que la cuenta Google ya este vinculada.

Debes completar el flujo OAuth del usuario:

1. ejecutar `auth_google_begin`
2. copiar `authorization_url`
3. abrir esa URL en un navegador
4. iniciar sesion en Google
5. aceptar permisos
6. dejar que Google redirija al callback del servidor
7. volver a OpenCode
8. ejecutar `auth_google_status`

Resultado esperado aproximado:

```json
{
  "connected": true,
  "google_email": "tu-cuenta@gmail.com",
  "scopes": ["..."],
  "status": "active"
}
```

## Paso 8: probar una tool real desde OpenCode

Despues de completar OAuth, prueba una tool de bajo riesgo.

Ejemplo recomendado:

- `calendar_list_calendars`

Luego puedes probar:

- `tasks_list_tasklists`
- `gmail_list_messages`

Despues continua con operaciones de escritura controladas como:

- `calendar_create_event`
- `tasks_create_tasklist`
- `gmail_create_draft`

## Paso 9: entender como identifica al usuario

Este MCP no acepta `user_id`, `google_email` ni identificadores manuales por argumento para decidir sobre quien actuar.

La identidad se resuelve desde el JWT del cliente MCP, concretamente desde el claim `sub`.

Eso significa:

- en local, `local-dev-token` representa al usuario de prueba
- en una integracion real, OpenCode deberia enviar un JWT real por usuario final

## Paso 10: diferencias entre prueba local y produccion

### En local

- URL MCP: `http://localhost:8000/mcp`
- token: `local-dev-token`
- `JWT_TEST_MODE=true`
- OAuth Google real opcional o requerido segun la prueba

### En staging o produccion

- URL MCP: la publica de tu despliegue
- token: JWT real emitido por tu plataforma
- `JWT_TEST_MODE=false`
- `ALLOWED_ORIGINS` ajustado a origenes reales
- `GOOGLE_REDIRECT_URI` publica y registrada en Google Cloud Console

## Problemas comunes

### OpenCode no conecta al MCP

Revisa:

- que el servidor este levantado
- que `http://localhost:8000/health` responda
- que la URL MCP usada sea `http://localhost:8000/mcp`
- que el transporte sea `streamable-http`

### OpenCode devuelve `401 unauthorized_client`

Revisa:

- que el header exista
- que uses exactamente `Authorization: Bearer local-dev-token`
- que `JWT_TEST_MODE=true` siga activo si estas en local

### OpenCode devuelve `403 origin_not_allowed`

Revisa `ALLOWED_ORIGINS` en `.env`.

Si OpenCode hace la llamada desde un origen web distinto, debes agregarlo ahi y reiniciar el servidor.

Ejemplo:

```env
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000
```

### OpenCode lista tools pero Google falla

Esto normalmente significa que el MCP funciona pero el usuario aun no completo OAuth Google.

Haz esto:

1. ejecuta `auth_google_begin`
2. completa consentimiento en navegador
3. ejecuta `auth_google_status`

### `auth_google_status` sigue en `connected: false`

Revisa:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- scopes concedidos
- que el callback llegue al servidor correcto

### Una tool Gmail, Calendar o Tasks devuelve error de permisos

Revisa:

- scopes configurados en `GOOGLE_OAUTH_SCOPES`
- scopes concedidos realmente por Google
- si necesitas reconectar la cuenta despues de cambiar scopes

## Secuencia minima recomendada

Si quieres el camino mas corto posible:

1. levantar el servidor
2. comprobar `/health`
3. validar `http://localhost:8000/mcp` con MCP Inspector
4. crear el servidor MCP remoto en OpenCode
5. probar `auth_google_status`
6. ejecutar `auth_google_begin`
7. completar OAuth en el navegador
8. volver a probar `auth_google_status`
9. probar `calendar_list_calendars`

## Referencias utiles

- `README.md`
- `docs/06-guia-desarrollo-local.md`
- `docs/08-validacion-manual-google-real.md`
- `docs/11-guia-tecnica-de-pruebas.md`
- `docs/02-autenticacion-y-seguridad.md`
- `docs/14-guia-reaccion-del-agente-ante-errores-mcp.md`
- `docs/16-system-prompt-opencode-errores-mcp.md`
- `docs/17-reglas-automaticas-agente-errores-mcp.yaml`
