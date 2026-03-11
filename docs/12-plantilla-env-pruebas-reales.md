# Plantilla `.env` para pruebas reales

## Objetivo

Esta plantilla sirve como referencia tecnica para construir un `.env` realista de pruebas. No debes copiar secretos reales al repositorio; usa este documento como guia.

## Ejemplo de `.env`

```env
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
APP_BASE_URL=http://localhost:8000

DATABASE_URL=sqlite:///./data/dev.db

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

TOKEN_ENCRYPTION_KEY=<FERNET_KEY_REAL>

GOOGLE_CLIENT_ID=<GOOGLE_OAUTH_CLIENT_ID>
GOOGLE_CLIENT_SECRET=<GOOGLE_OAUTH_CLIENT_SECRET>
GOOGLE_REDIRECT_URI=http://localhost:8000/oauth/google/callback
GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS=10
GOOGLE_OAUTH_SCOPES=https://www.googleapis.com/auth/calendar,https://www.googleapis.com/auth/tasks,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.compose,https://www.googleapis.com/auth/gmail.modify,openid,email,profile

JWT_ISSUER=http://localhost:8000/auth/dev
JWT_AUDIENCE=google-mcp-server
JWT_ALGORITHMS=HS256,RS256
JWT_JWKS_URL=
JWT_PUBLIC_KEY=
JWT_SHARED_SECRET=

JWT_TEST_MODE=true
JWT_TEST_TOKEN=local-dev-token
JWT_TEST_SUBJECT=manual-test-user
```

## Como rellenar cada campo importante

### `DATABASE_URL`

Para prueba rapida local:

```env
DATABASE_URL=sqlite:///./data/dev.db
```

Para Compose o Postgres local:

```env
DATABASE_URL=postgresql+psycopg://mcp_google:mcp_google@localhost:5432/mcp_google
```

### `TOKEN_ENCRYPTION_KEY`

Debe ser una clave Fernet valida.

Puedes generar una con:

```bash
.venv/bin/python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

### `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`

Salen del `OAuth Client ID` creado en Google Cloud Console.

### `GOOGLE_REDIRECT_URI`

Debe coincidir exactamente con la URI registrada en Google Cloud Console.

Ejemplo local:

```env
GOOGLE_REDIRECT_URI=http://localhost:8000/oauth/google/callback
```

### `ALLOWED_ORIGINS`

Lista de origenes validos para requests al endpoint MCP remoto.

Ejemplo local:

```env
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

### `JWT_TEST_MODE`

Para prueba inicial local puedes dejar:

```env
JWT_TEST_MODE=true
JWT_TEST_TOKEN=local-dev-token
JWT_TEST_SUBJECT=manual-test-user
```

Para entornos mas reales:

- `JWT_TEST_MODE=false`
- configura `JWT_JWKS_URL` o `JWT_PUBLIC_KEY`

### `REQUIRE_EXPLICIT_APPROVAL`

Para primera prueba real:

```env
REQUIRE_EXPLICIT_APPROVAL=false
```

Cuando quieras probar tools sensibles con politica mas realista:

```env
REQUIRE_EXPLICIT_APPROVAL=true
```

En ese caso, tu JWT real debe incluir `approved_tools`.

## Checklist de revision del `.env`

- [ ] `GOOGLE_CLIENT_ID` completo
- [ ] `GOOGLE_CLIENT_SECRET` completo
- [ ] `GOOGLE_REDIRECT_URI` coincide exactamente con Google Cloud Console
- [ ] `TOKEN_ENCRYPTION_KEY` es una clave Fernet valida
- [ ] `ALLOWED_ORIGINS` incluye el origen que usaras
- [ ] `JWT_TEST_MODE` esta segun el tipo de prueba que quieres hacer
- [ ] `REQUIRE_EXPLICIT_APPROVAL` esta segun el nivel de seguridad que quieres probar

## Recomendacion practica

Para la primera validacion real usa:

- `SQLite`
- `JWT_TEST_MODE=true`
- `REQUIRE_EXPLICIT_APPROVAL=false`

Despues repite con:

- `Postgres`
- `JWT_TEST_MODE=false` si ya tienes emisor real
- `REQUIRE_EXPLICIT_APPROVAL=true`
