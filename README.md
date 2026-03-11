# MCP Google Server

Servidor MCP remoto en Python para integrar Google Calendar, Google Tasks y Gmail en flujos de agentes multiusuario.

## Stack

- `Python 3.11+`
- `FastMCP`
- `Starlette`
- `SQLAlchemy` + `Alembic`
- `google-api-python-client`
- `google-auth`
- `google-auth-oauthlib`

## Funcionalidad actual

- autenticacion del cliente con `Bearer JWT`
- una cuenta Google conectada por usuario
- OAuth Google por usuario
- CRUD para Calendar
- CRUD para Tasks
- lectura, drafts, envio y borrado para Gmail
- auditoria basica
- rate limiting basico
- aprobacion explicita opcional para tools sensibles

## Estructura principal

- `app/`: codigo fuente del servidor
- `docs/`: planificacion, guias locales, despliegue y pruebas E2E
- `migrations/`: migraciones Alembic
- `tests/`: suite unitaria actual

## Arranque rapido local

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
python -m app.main
```

Healthcheck:

```bash
curl http://localhost:8000/health
```

## Arranque con Docker

```bash
docker build -t mcp-google:local .
docker run --rm -p 8000:8000 --env-file .env mcp-google:local
```

## Arranque con Docker Compose

```bash
docker compose up --build
```

Esto levanta:

- `postgres`
- `mcp-google`

## Variables importantes

- `DATABASE_URL`
- `TOKEN_ENCRYPTION_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- `JWT_ISSUER`
- `JWT_AUDIENCE`
- `JWT_JWKS_URL` o `JWT_PUBLIC_KEY`
- `ALLOWED_ORIGINS`
- `RATE_LIMIT_ENABLED`
- `RATE_LIMIT_RPM`
- `REQUIRE_EXPLICIT_APPROVAL`
- `APPROVAL_REQUIRED_TOOLS`

## Flujo basico de prueba

1. levantar el servidor
2. probar `/health`
3. iniciar `GET /oauth/google/start` con bearer token
4. abrir `authorization_url`
5. confirmar `GET /oauth/google/status`
6. probar tools MCP desde Inspector o cliente Python

## Documentacion

- `docs/06-guia-desarrollo-local.md`
- `docs/07-despliegue-y-pruebas-e2e.md`
- `docs/02-autenticacion-y-seguridad.md`

## Tests

```bash
pytest
```
