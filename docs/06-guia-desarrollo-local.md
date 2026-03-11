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
RATE_LIMIT_ENABLED=true
RATE_LIMIT_RPM=120
LOG_LEVEL=INFO
LOG_JSON=false
REQUIRE_EXPLICIT_APPROVAL=false
APPROVAL_REQUIRED_TOOLS=gmail_send_email,gmail_delete_message,calendar_delete_event,tasks_delete_task,tasks_delete_tasklist
MCP_SERVER_NAME=google-mcp-server
MCP_SERVER_VERSION=0.1.0
MCP_PATH=/mcp
JWT_ISSUER=http://localhost:8000/auth/dev
JWT_AUDIENCE=google-mcp-server
JWT_TEST_TOKEN=local-dev-token
JWT_TEST_MODE=true
JWT_TEST_SUBJECT=local-dev-user
GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS=10
```

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

Instalar y ejecutar:

```bash
npx @modelcontextprotocol/inspector
```

Luego conectar el inspector a:

- URL: `http://localhost:8000/mcp`
- Header: `Authorization: Bearer local-dev-token`

Si tu cliente envia header `Origin`, debe coincidir con alguno de `ALLOWED_ORIGINS`.

Acciones sugeridas:

- `List Tools`
- ejecutar `ping`

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
5. probar MCP con `ping`
6. continuar con la siguiente fase de implementacion
