# Resumen y arquitectura

## Objetivo

Construir un servidor MCP remoto en `Python` usando `FastMCP` para exponer operaciones sobre Google Calendar, Google Tasks y Gmail. El servidor debe ser multiusuario, operar con una cuenta Google por usuario y estar preparado para que agentes externos consuman sus tools mediante autenticacion propia del cliente.

## Alcance funcional de v1

- Google Calendar:
  - listar calendarios
  - listar eventos
  - obtener detalle de evento
  - crear evento
  - actualizar evento
  - eliminar evento
- Google Tasks:
  - listar tasklists
  - crear tasklist
  - actualizar tasklist
  - eliminar tasklist
  - listar tasks
  - crear task
  - actualizar task
  - completar task
  - eliminar task
- Gmail:
  - listar mensajes
  - leer mensaje
  - listar hilos
  - crear draft
  - actualizar draft
  - eliminar draft
  - enviar email
  - eliminar mensaje

## Decisiones clave

- Transporte remoto: `streamable-http`.
- Runtime MCP: `FastMCP`.
- Lenguaje: `Python`.
- Persistencia: `PostgreSQL`.
- Modelo multiusuario: una sola cuenta Google conectada por usuario.
- Autenticacion cliente-servidor: `Bearer JWT` emitido por la plataforma que consume el MCP.
- Autenticacion Google: OAuth 2.0 Authorization Code Flow con PKCE.

## Enfoque recomendado

- Un unico servidor MCP modular en lugar de tres servidores separados.
- Separacion interna por dominios: `calendar`, `tasks`, `gmail`, `auth`.
- Montaje como aplicacion ASGI para combinar:
  - endpoint MCP remoto
  - endpoints HTTP auxiliares para OAuth
  - healthchecks y observabilidad

## Arquitectura por capas

### Capa MCP

- Registra tools con `FastMCP`.
- Expone herramientas remotas por `streamable-http`.
- Se integra con el contexto autenticado del request.

### Capa HTTP auxiliar

- `GET /health`
- `GET /oauth/google/start`
- `GET /oauth/google/callback`
- `POST /oauth/google/disconnect` opcional

### Capa de identidad

- Valida el token JWT del cliente.
- Extrae `sub` como identidad estable del usuario.
- Construye `RequestContext` por request.

### Capa Google OAuth

- Genera URL de consentimiento.
- Intercambia `code` por tokens.
- Guarda tokens cifrados.
- Refresca access tokens automaticamente.

### Capa de persistencia

- Guarda usuarios, conexiones Google, estados OAuth y auditoria.
- Usa cifrado para access y refresh tokens.

### Capa de dominio

- Wrappers y servicios para Calendar, Tasks y Gmail.
- Reglas de validacion, normalizacion y manejo de errores.

### Capa de seguridad y observabilidad

- Rate limiting.
- Auditoria de tool calls.
- Redaccion de secretos.
- Allow-list de tools si se activa por configuracion.

## Estructura de proyecto propuesta

```text
app/
  main.py
  asgi.py
  config.py
  logging.py
  security/
    jwt_auth.py
    encryption.py
    rate_limit.py
  context/
    request_context.py
  db/
    models.py
    session.py
    repositories/
  oauth/
    google_oauth.py
    state_store.py
  google/
    credentials.py
    calendar_client.py
    tasks_client.py
    gmail_client.py
  schemas/
    common.py
    auth.py
    calendar.py
    tasks.py
    gmail.py
  services/
    auth_service.py
    connection_service.py
    audit_service.py
    calendar_service.py
    tasks_service.py
    gmail_service.py
  tools/
    auth_tools.py
    calendar_tools.py
    tasks_tools.py
    gmail_tools.py
tests/
  unit/
  integration/
  e2e/
```

## Razon de esta arquitectura

- Permite empezar rapido con un solo endpoint MCP.
- Mantiene el codigo separado por responsabilidad.
- Facilita pasar a varios servidores MCP en el futuro si la operacion lo requiere.
- Reduce complejidad inicial comparado con separar Calendar, Tasks y Gmail desde v1.
