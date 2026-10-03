# Checklist de prerrequisitos para prueba real

> Configuración actual: [permisos persistentes](23-permisos-persistentes.md).
> En `server_policy`, habilitar `read_write` una vez y conservar el JWT; `permission_denied`
> requiere un cambio administrativo. Las instrucciones de `approved_tools`,
> `approval_required` y las variables antiguas de aprobación de esta guía describen
> exclusivamente el modo heredado `jwt_claims`. La confirmación de operaciones es técnica.

## Objetivo

Este checklist te ayuda a confirmar que ya tienes todo lo necesario antes de iniciar una prueba real del servidor MCP con Google Calendar, Google Tasks y Gmail.

## Checklist de entorno local

- [x ] Tengo `Python 3.11+` instalado o usare `Docker` / `Docker Compose`.
- [x ] Tengo acceso a una terminal dentro del proyecto.
- [x ] Tengo un puerto libre para la app, normalmente `8000`.
- [x ] Puedo abrir el navegador localmente para completar el consentimiento Google OAuth.

## Checklist de proyecto local

- [x ] El repositorio ya esta descargado en mi maquina.
- [x ] Ya cree el entorno virtual `.venv` o usare contenedores.
- [x ] Ya instale dependencias con `pip install -e ".[dev]"` o usare Docker.
- [x ] Ya tengo un archivo `.env` basado en `.env.example`.

## Checklist de base de datos

### Opcion rapida

- [x ] Voy a usar `SQLite` con `DATABASE_URL=sqlite:///./data/dev.db`.

### Opcion recomendada para pruebas mas reales

- [ ] Voy a usar `Postgres` con `docker compose`.
- [ ] El contenedor de Postgres puede arrancar en `localhost:5432`.

## Checklist de Google Cloud Console

- [X ] Cree o reutilice un proyecto en Google Cloud.
- [x ] Habilite `Google Calendar API`.
- [x ] Habilite `Google Tasks API`.
- [x ] Habilite `Gmail API`.
- [x ] Configure la pantalla de consentimiento OAuth.
- [x ] Cree un `OAuth Client ID` de tipo `Web application`.

## Checklist de pantalla de consentimiento

- [x ] Defini el nombre de la aplicacion.
- [x ] Defini el correo de soporte.
- [x ] Agregue usuarios de prueba si la app esta en modo testing.
- [x ] Agregue los scopes requeridos.

## Checklist de scopes Google

- [x ] `openid`
- [x ] `email`
- [x ] `profile`
- [x ] `https://www.googleapis.com/auth/calendar`
- [x ] `https://www.googleapis.com/auth/tasks`
- [x ] `https://www.googleapis.com/auth/gmail.readonly`
- [x ] `https://www.googleapis.com/auth/gmail.compose`
- [x ] `https://www.googleapis.com/auth/gmail.modify`

## Checklist de redirect URIs

### Para local

- [x ] `http://localhost:8000/oauth/google/callback`

### Para remoto, si aplica

- [ ] `https://tu-dominio/oauth/google/callback`

## Checklist de variables de entorno obligatorias

- [ ] `APP_ENV`
- [ ] `APP_HOST`
- [ ] `APP_PORT`
- [ ] `APP_BASE_URL`
- [ ] `DATABASE_URL`
- [ ] `TOKEN_ENCRYPTION_KEY`
- [ ] `GOOGLE_CLIENT_ID`
- [ ] `GOOGLE_CLIENT_SECRET`
- [ ] `GOOGLE_REDIRECT_URI`
- [ ] `GOOGLE_OAUTH_SCOPES`
- [ ] `JWT_ISSUER`
- [ ] `JWT_AUDIENCE`

## Checklist de variables recomendadas para pruebas locales

- [ ] `JWT_TEST_MODE=true`
- [ ] `JWT_TEST_TOKEN=local-dev-token`
- [ ] `JWT_TEST_SUBJECT=manual-test-user`
- [ ] `ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000`
- [ ] `RATE_LIMIT_ENABLED=true`
- [ ] `RATE_LIMIT_RPM=120`
- [ ] `REQUIRE_EXPLICIT_APPROVAL=false` para la primera prueba real

## Checklist de cuentas de prueba

- [x ] Tengo una cuenta Google real para vincular.
- [x ] Esa cuenta tiene acceso a Calendar.
- [x ] Esa cuenta tiene acceso a Tasks.
- [x ] Esa cuenta tiene acceso a Gmail.
- [x ] Idealmente no es una cuenta personal critica.

## Checklist de identidad del cliente MCP

### Para prueba simple

- [x ] Voy a usar `JWT_TEST_MODE=true`.
- [x ] Voy a autenticar con `Authorization: Bearer local-dev-token`.

### Para prueba mas realista

- [ ] Tengo un JWT real emitido por mi plataforma.
- [ ] Ese JWT contiene `sub` estable por usuario.
- [ ] Si quiero probar aprobaciones, el JWT puede incluir `approved_tools`.

## Checklist de arranque

- [ ] Puedo ejecutar `alembic upgrade head`.
- [ ] Puedo levantar el servidor con `python -m app.main` o `docker compose up --build`.
- [ ] `/health` responde correctamente.
- [ ] `scripts/mcp_smoke_test.py` lista las tools MCP.

## Checklist previo a tools sensibles

- [ ] Ya valide `auth_google_status`.
- [ ] Ya valide Calendar y Tasks basicos.
- [ ] Ya decidi si usare `REQUIRE_EXPLICIT_APPROVAL=true` o `false`.
- [ ] Si activare aprobaciones, ya tengo forma de emitir JWT con `approved_tools`.

## Criterio de listo para probar

Puedes pasar a la prueba real cuando:

- [ ] el servidor levanta
- [ ] `/health` responde
- [ ] tienes `authorization_url` desde `/oauth/google/start`
- [ ] la cuenta Google de prueba existe y puede dar consentimiento
