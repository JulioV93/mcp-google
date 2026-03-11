# Despliegue y pruebas E2E

## Objetivo

Esta guia explica como ejecutar el servidor MCP con Docker, como configurar Google OAuth para una prueba real y como validar el flujo end-to-end con un cliente MCP.

## Requisitos

- Docker instalado
- una aplicacion OAuth 2.0 en Google Cloud Console
- variables de entorno completas para JWT, cifrado y Google OAuth

## Construir la imagen Docker

Desde la raiz del proyecto:

```bash
docker build -t mcp-google:local .
```

## Ejecutar el contenedor localmente

```bash
docker run --rm -p 8000:8000 --env-file .env mcp-google:local
```

## Ejecutar con Docker Compose

Para levantar la aplicacion junto con Postgres local:

```bash
docker compose up --build
```

Servicios levantados:

- `postgres` en `localhost:5432`
- `mcp-google` en `http://localhost:8000`

La configuracion de `docker-compose.yml` fuerza `DATABASE_URL` a un Postgres local para pruebas mas realistas.

## Variables minimas para despliegue real

- `APP_ENV=production`
- `APP_HOST=0.0.0.0`
- `APP_PORT=8000`
- `APP_BASE_URL=https://tu-dominio`
- `DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname`
- `ALLOWED_ORIGINS=https://tu-dominio`
- `TOKEN_ENCRYPTION_KEY=<fernet-key>`
- `GOOGLE_CLIENT_ID=<oauth-client-id>`
- `GOOGLE_CLIENT_SECRET=<oauth-client-secret>`
- `GOOGLE_REDIRECT_URI=https://tu-dominio/oauth/google/callback`
- `GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS=10`
- `GOOGLE_OAUTH_SCOPES=...`
- `JWT_ISSUER=<issuer-real>`
- `JWT_AUDIENCE=<audience-real>`
- `JWT_JWKS_URL=<jwks-url>` o `JWT_PUBLIC_KEY=<public-key>`
- `RATE_LIMIT_ENABLED=true`
- `RATE_LIMIT_RPM=120`
- `REQUIRE_EXPLICIT_APPROVAL=true|false`
- `APPROVAL_REQUIRED_TOOLS=gmail_send_email,gmail_delete_message,...`

## Configurar Google OAuth

En Google Cloud Console:

1. crea o reutiliza un proyecto
2. habilita estas APIs:
   - Google Calendar API
   - Google Tasks API
   - Gmail API
3. crea un `OAuth Client ID` de tipo `Web application`
4. registra las redirect URIs autorizadas

Para entorno local:

- `http://localhost:8000/oauth/google/callback`

Para remoto:

- `https://tu-dominio/oauth/google/callback`

## Configurar la pantalla de consentimiento

- define nombre de aplicacion
- define scopes necesarios
- agrega usuarios de prueba si la app no esta publicada

Scopes recomendados para esta v1:

- `openid`
- `email`
- `profile`
- `https://www.googleapis.com/auth/calendar`
- `https://www.googleapis.com/auth/tasks`
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.compose`
- `https://www.googleapis.com/auth/gmail.modify`

## Consideraciones de seguridad remota

- configura `ALLOWED_ORIGINS` con los origenes reales que llamaran al endpoint MCP
- no uses `*` en produccion para origenes del endpoint MCP
- manten `TOKEN_ENCRYPTION_KEY` fuera del repositorio
- usa `JWT_JWKS_URL` o `JWT_PUBLIC_KEY` reales en lugar del modo de prueba
- activa aprobaciones explicitas si tus agentes pueden invocar tools sensibles

## Aplicar migraciones antes de levantar en remoto

```bash
alembic upgrade head
```

Si usas Docker y quieres correr migraciones manualmente:

```bash
docker run --rm --env-file .env mcp-google:local alembic upgrade head
```

Si usas Docker Compose y necesitas aplicar migraciones desde el contenedor:

```bash
docker compose run --rm mcp-google alembic upgrade head
```

## Flujo E2E recomendado

### 1. Levantar el servidor

Local con Python:

```bash
source .venv/bin/activate
python -m app.main
```

O con Docker:

```bash
docker run --rm -p 8000:8000 --env-file .env mcp-google:local
```

### 2. Verificar healthcheck

```bash
curl http://localhost:8000/health
```

### 3. Iniciar el flujo OAuth Google

```bash
curl -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/start
```

La respuesta devolvera una `authorization_url`.

### 4. Abrir la URL en navegador

- inicia sesion con la cuenta Google de prueba
- concede permisos
- deja que Google redirija a `/oauth/google/callback`

### 5. Confirmar estado de conexion

```bash
curl -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/status
```

Deberias ver `connected: true` y el email Google vinculado.

### 6. Probar tools MCP

Con MCP Inspector:

```bash
npx @modelcontextprotocol/inspector
```

Conectar a:

- `http://localhost:8000/mcp`
- header `Authorization: Bearer local-dev-token`
- si el cliente envia `Origin`, debe coincidir con `ALLOWED_ORIGINS`

Orden sugerido:

1. `auth_google_status`
2. `calendar_list_calendars`
3. `tasks_list_tasklists`
4. `gmail_list_messages`

Si activas `REQUIRE_EXPLICIT_APPROVAL=true`, las tools sensibles deberan venir autorizadas desde la identidad del cliente mediante el claim `approved_tools`.

## Ejemplos de prueba funcional

### Calendar

- crear un evento con `calendar_create_event`
- listar con `calendar_list_events`
- editar con `calendar_update_event`
- eliminar con `calendar_delete_event`

### Tasks

- crear lista con `tasks_create_tasklist`
- crear tarea con `tasks_create_task`
- completar con `tasks_complete_task`
- borrar con `tasks_delete_task`

### Gmail

- listar mensajes con `gmail_list_messages`
- crear draft con `gmail_create_draft`
- actualizar draft con `gmail_update_draft`
- enviar correo con `gmail_send_email`

## Flujo de aprobacion recomendado

Para herramientas sensibles:

1. el agente solicita ejecutar una tool de alto riesgo
2. la plataforma de agentes decide si requiere aprobacion humana
3. si se aprueba, la plataforma emite o reemite un JWT con `approved_tools`
4. el cliente repite la llamada usando ese JWT

Tools sensibles iniciales:

- `gmail_send_email`
- `gmail_delete_message`
- `calendar_delete_event`
- `tasks_delete_task`
- `tasks_delete_tasklist`

## Despliegue remoto sugerido

Opciones simples:

- Render
- Railway
- Fly.io
- VPS con Docker

Requisitos minimos del host:

- HTTPS
- dominio publico
- base de datos Postgres
- variables secretas seguras

## Checklist de salida

- `/health` responde correctamente
- `alembic upgrade head` aplica sin errores
- OAuth Google completa el callback
- `auth_google_status` devuelve conexion activa
- Calendar, Tasks y Gmail responden desde un cliente MCP real
- logs no muestran secretos
- rate limiting responde `429` cuando corresponde
- origenes no permitidos reciben `403 origin_not_allowed`
- tools sensibles exigen aprobacion si esa politica esta activa
