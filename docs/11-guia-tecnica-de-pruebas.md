# Guia tecnica de pruebas

> Configuración actual: [permisos persistentes](23-permisos-persistentes.md).
> En `server_policy`, habilitar `read_write` una vez y conservar el JWT; `permission_denied`
> requiere un cambio administrativo. Las instrucciones de `approved_tools`,
> `approval_required` y las variables antiguas de aprobación de esta guía describen
> exclusivamente el modo heredado `jwt_claims`. La confirmación de operaciones es técnica.

## Objetivo

Esta guia resume como probar tecnicamente el servidor MCP, que herramientas conviene usar para cada capa y que validar en cada una.

## Capas que debes probar

El proyecto tiene varias capas y no todas se prueban con la misma herramienta:

1. configuracion y arranque
2. endpoints HTTP auxiliares
3. autenticacion JWT
4. OAuth Google
5. endpoint MCP remoto
6. tools funcionales de Calendar, Tasks y Gmail
7. auditoria, seguridad y rate limiting

## Herramientas recomendadas

### 1. Terminal

Usala para:

- levantar el servidor
- ejecutar migraciones
- correr tests
- lanzar el smoke test MCP

Comandos base:

```bash
source .venv/bin/activate
alembic upgrade head
python -m app.main
pytest
```

### 2. `curl`

Usalo para:

- probar `/health`
- probar `/oauth/google/start`
- probar `/oauth/google/status`
- comprobar errores HTTP como `401`, `403`, `429`

Ejemplos:

```bash
curl http://localhost:8000/health
curl -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/status
curl -H "Authorization: Bearer local-dev-token" http://localhost:8000/oauth/google/start
```

### 3. `scripts/mcp_smoke_test.py`

Usalo para:

- confirmar que el endpoint MCP responde
- listar tools disponibles
- llamar tools con argumentos JSON

Ejemplos:

```bash
.venv/bin/python scripts/mcp_smoke_test.py
.venv/bin/python scripts/mcp_smoke_test.py --tool auth_google_status
.venv/bin/python scripts/mcp_smoke_test.py --tool calendar_list_calendars
```

### 4. MCP Inspector

Usalo para:

- inspeccionar tools de manera interactiva
- ejecutar llamadas manuales una por una
- revisar schemas y respuestas de las tools

Instalacion y arranque:

```bash
npx @modelcontextprotocol/inspector
```

Conecta con:

- URL: `http://localhost:8000/mcp`
- transport: `streamable-http`
- header: `Authorization: Bearer local-dev-token`

### 5. Navegador

Usalo para:

- abrir `authorization_url`
- completar consentimiento Google OAuth
- revisar el callback OAuth

### 6. Docker / Docker Compose

Usalo para:

- validar comportamiento con contenedores
- probar con Postgres local
- acercarte mas al entorno remoto

Comandos:

```bash
docker build -t mcp-google:local .
docker run --rm -p 8000:8000 --env-file .env mcp-google:local
docker compose up --build
```

### 7. `pytest`

Usalo para:

- validar que no rompiste el proyecto
- confirmar regresiones antes y despues de cambios

```bash
pytest
```

## Estrategia de prueba por nivel

### Nivel 1: smoke test tecnico

Objetivo:

- comprobar que el servidor levanta
- comprobar que `/health` responde
- comprobar que el endpoint MCP lista tools

Herramientas:

- terminal
- `curl`
- `scripts/mcp_smoke_test.py`

Checklist:

- [ ] El servidor arranca sin error
- [ ] `/health` responde `200`
- [ ] `mcp_smoke_test.py` lista tools

### Nivel 2: prueba de autenticacion

Objetivo:

- comprobar que sin token falla
- comprobar que con token valido responde
- comprobar que `Origin` se valida si aplica

Herramientas:

- `curl`
- MCP Inspector

Checklist:

- [ ] MCP sin token devuelve `401`
- [ ] MCP con token valido responde
- [ ] origen invalido devuelve `403 origin_not_allowed`

### Nivel 3: prueba OAuth Google

Objetivo:

- obtener `authorization_url`
- completar consentimiento
- confirmar `connected: true`

Herramientas:

- `curl`
- navegador

Checklist:

- [ ] `/oauth/google/start` devuelve URL valida
- [ ] la pantalla de consentimiento abre correctamente
- [ ] `/oauth/google/status` devuelve `connected: true`

### Nivel 4: prueba funcional por servicio

Objetivo:

- validar Calendar
- validar Tasks
- validar Gmail

Herramientas:

- `scripts/mcp_smoke_test.py`
- MCP Inspector

Checklist Calendar:

- [ ] `calendar_list_calendars`
- [ ] `calendar_create_event`
- [ ] `calendar_list_events`
- [ ] `calendar_delete_event`

Checklist Tasks:

- [ ] `tasks_create_tasklist`
- [ ] `tasks_create_task`
- [ ] `tasks_complete_task`
- [ ] `tasks_delete_task`

Checklist Gmail:

- [ ] `gmail_list_messages`
- [ ] `gmail_create_draft`
- [ ] `gmail_update_draft`
- [ ] `gmail_send_email` opcional

### Nivel 5: prueba de seguridad y operacion

Objetivo:

- validar auditoria
- validar rate limiting
- validar aprobaciones explicitas si se activan

Herramientas:

- `curl`
- logs
- base de datos

Checklist:

- [ ] se generan registros en `audit_logs`
- [ ] no aparecen tokens o cuerpos sensibles en logs
- [ ] el rate limit devuelve `429`
- [ ] una tool sensible exige aprobacion si `REQUIRE_EXPLICIT_APPROVAL=true`

## Herramientas segun el tipo de prueba

### Si quieres validar rapido

Usa:

- `curl`
- `scripts/mcp_smoke_test.py`

### Si quieres explorar tools manualmente

Usa:

- MCP Inspector

### Si quieres acercarte a produccion

Usa:

- Docker Compose
- Postgres local

### Si quieres validar que no rompiste el codigo

Usa:

- `pytest`

## Orden recomendado de prueba

1. `pytest`
2. `/health`
3. smoke test MCP
4. `/oauth/google/start`
5. `/oauth/google/status`
6. Calendar
7. Tasks
8. Gmail
9. seguridad y auditoria

## Problemas comunes y herramienta adecuada

### El servidor no arranca

Usa:

- terminal
- logs del proceso

### OAuth no redirige bien

Usa:

- navegador
- `curl`
- revision de `GOOGLE_REDIRECT_URI`

### MCP no responde como esperas

Usa:

- `scripts/mcp_smoke_test.py`
- MCP Inspector

### Una tool devuelve error raro del proveedor

Usa:

- MCP Inspector
- logs
- reintento manual con payload minimo

### Sospechas problema de seguridad

Usa:

- `curl`
- logs
- revision de `audit_logs`
