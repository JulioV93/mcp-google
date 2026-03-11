# Backlog de implementacion

## Backlog general

### Bootstrap del proyecto

- crear proyecto Python con `pyproject.toml`
- definir estructura `app/`, `tests/`, `migrations/`
- configurar ASGI app base
- exponer healthcheck y endpoint MCP

### Configuracion y runtime

- centralizar settings con variables de entorno
- definir entornos `local`, `staging`, `prod`
- logging estructurado con redaccion de secretos

### Autenticacion del cliente MCP

- validar `Bearer JWT`
- soportar `issuer` y `audience`
- soporte para JWKS remoto o clave publica fija
- construir `RequestContext` por request

### Persistencia

- definir modelos de base de datos
- crear migracion inicial
- crear repositorios de usuarios, conexiones Google, estados OAuth y auditoria

### OAuth Google multiusuario

- generar URL de autorizacion
- guardar `state` y `code_verifier`
- callback de intercambio de tokens
- persistencia cifrada
- refresh automatico
- revocacion y desconexion

### Clientes Google

- factoria de credenciales desde tokens persistidos
- cliente Calendar
- cliente Tasks
- cliente Gmail
- manejo homogeneo de errores Google

### Tools MCP

- tools de auth
- tools de Calendar
- tools de Tasks
- tools de Gmail

### Seguridad operativa

- rate limiting
- allow-list de tools
- auditoria
- validacion estricta Pydantic
- redaccion de contenido sensible

### Testing

- unit tests
- integration tests con mocks de Google
- pruebas de aislamiento multiusuario
- pruebas MCP end-to-end

## Backlog por archivos y modulos

### Nucleo de aplicacion

- `app/main.py`
- `app/asgi.py`
- `app/config.py`
- `app/logging.py`

### Seguridad

- `app/security/jwt_auth.py`
- `app/security/encryption.py`
- `app/security/rate_limit.py`

### Contexto

- `app/context/request_context.py`

### Base de datos

- `app/db/session.py`
- `app/db/models.py`
- `app/db/repositories/users.py`
- `app/db/repositories/google_connections.py`
- `app/db/repositories/audit_logs.py`
- `app/db/repositories/oauth_states.py`

### OAuth

- `app/oauth/google_oauth.py`
- `app/oauth/state_store.py`

### Google

- `app/google/credentials.py`
- `app/google/calendar_client.py`
- `app/google/tasks_client.py`
- `app/google/gmail_client.py`

### Schemas

- `app/schemas/common.py`
- `app/schemas/auth.py`
- `app/schemas/calendar.py`
- `app/schemas/tasks.py`
- `app/schemas/gmail.py`

### Servicios

- `app/services/auth_service.py`
- `app/services/connection_service.py`
- `app/services/audit_service.py`
- `app/services/calendar_service.py`
- `app/services/tasks_service.py`
- `app/services/gmail_service.py`

### Tools

- `app/tools/auth_tools.py`
- `app/tools/calendar_tools.py`
- `app/tools/tasks_tools.py`
- `app/tools/gmail_tools.py`

### Tests

- `tests/unit/`
- `tests/integration/`
- `tests/e2e/`

## Orden exacto de implementacion

### Fase 1: Foundation

- proyecto Python
- settings
- logging
- ASGI base
- FastMCP base
- `/health`

### Fase 2: Identidad del cliente

- middleware JWT
- `RequestContext`
- proteger acceso al endpoint MCP

### Fase 3: Base de datos

- modelos
- migracion inicial
- repositorios

### Fase 4: OAuth Google

- start
- callback
- status
- disconnect
- state y PKCE
- persistencia cifrada

### Fase 5: Capa Google comun

- credenciales refreshables
- wrapper comun de errores
- utilidad de auditoria

### Fase 6: Calendar

- clientes
- schemas
- service
- tools

### Fase 7: Tasks

- clientes
- schemas
- service
- tools

### Fase 8: Gmail

- MIME y base64url
- drafts
- send
- delete

### Fase 9: Hardening

- rate limiting
- allow-list
- redaccion y auditoria

### Fase 10: Testing final

- unit
- integration
- E2E MCP

## Dependencias criticas

- JWT antes de cualquier tool multiusuario real
- base de datos antes de OAuth Google
- OAuth Google antes de Calendar, Tasks y Gmail
- `google/credentials.py` antes de clientes de servicio
- Gmail despues de la capa comun de Google
