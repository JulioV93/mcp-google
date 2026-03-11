# Checklist de prerrequisitos para prueba real

## Objetivo

Este checklist te ayuda a confirmar que ya tienes todo lo necesario antes de iniciar una prueba real del servidor MCP con Google Calendar, Google Tasks y Gmail.

## Checklist de entorno local

- [ ] Tengo `Python 3.11+` instalado o usare `Docker` / `Docker Compose`.
- [ ] Tengo acceso a una terminal dentro del proyecto.
- [ ] Tengo un puerto libre para la app, normalmente `8000`.
- [ ] Puedo abrir el navegador localmente para completar el consentimiento Google OAuth.

## Checklist de proyecto local

- [ ] El repositorio ya esta descargado en mi maquina.
- [ ] Ya cree el entorno virtual `.venv` o usare contenedores.
- [ ] Ya instale dependencias con `pip install -e ".[dev]"` o usare Docker.
- [ ] Ya tengo un archivo `.env` basado en `.env.example`.

## Checklist de base de datos

### Opcion rapida

- [ ] Voy a usar `SQLite` con `DATABASE_URL=sqlite:///./data/dev.db`.

### Opcion recomendada para pruebas mas reales

- [ ] Voy a usar `Postgres` con `docker compose`.
- [ ] El contenedor de Postgres puede arrancar en `localhost:5432`.

## Checklist de Google Cloud Console

- [ ] Cree o reutilice un proyecto en Google Cloud.
- [ ] Habilite `Google Calendar API`.
- [ ] Habilite `Google Tasks API`.
- [ ] Habilite `Gmail API`.
- [ ] Configure la pantalla de consentimiento OAuth.
- [ ] Cree un `OAuth Client ID` de tipo `Web application`.

## Checklist de pantalla de consentimiento

- [ ] Defini el nombre de la aplicacion.
- [ ] Defini el correo de soporte.
- [ ] Agregue usuarios de prueba si la app esta en modo testing.
- [ ] Agregue los scopes requeridos.

## Checklist de scopes Google

- [ ] `openid`
- [ ] `email`
- [ ] `profile`
- [ ] `https://www.googleapis.com/auth/calendar`
- [ ] `https://www.googleapis.com/auth/tasks`
- [ ] `https://www.googleapis.com/auth/gmail.readonly`
- [ ] `https://www.googleapis.com/auth/gmail.compose`
- [ ] `https://www.googleapis.com/auth/gmail.modify`

## Checklist de redirect URIs

### Para local

- [ ] `http://localhost:8000/oauth/google/callback`

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

- [ ] Tengo una cuenta Google real para vincular.
- [ ] Esa cuenta tiene acceso a Calendar.
- [ ] Esa cuenta tiene acceso a Tasks.
- [ ] Esa cuenta tiene acceso a Gmail.
- [ ] Idealmente no es una cuenta personal critica.

## Checklist de identidad del cliente MCP

### Para prueba simple

- [ ] Voy a usar `JWT_TEST_MODE=true`.
- [ ] Voy a autenticar con `Authorization: Bearer local-dev-token`.

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
