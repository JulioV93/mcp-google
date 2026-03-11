# Sprint plan v1

## Objetivo del sprint

Dejar operativo un servidor MCP remoto, multiusuario, con autenticacion por `Bearer JWT`, OAuth Google por usuario y soporte funcional inicial para Calendar, Tasks y Gmail.

## Alcance del sprint

- solo servidor MCP y backend asociado
- sin implementar agentes
- una cuenta Google por usuario

## Prioridades

### P0 - Imprescindible

#### P0.1 Foundation del proyecto

- crear estructura base del proyecto
- configurar `pyproject.toml`
- levantar app ASGI
- montar FastMCP en `streamable-http`
- exponer `GET /health`

Done:

- la app levanta localmente
- `/health` responde `200`
- el endpoint MCP existe

#### P0.2 Configuracion y observabilidad minima

- centralizar settings por env vars
- logging estructurado
- filtros para no imprimir secretos

Done:

- settings tipados cargan correctamente
- logs no exponen tokens ni secretos

#### P0.3 Autenticacion del cliente MCP

- validar `Bearer JWT`
- verificar `iss`, `aud`, `exp`
- resolver `sub`
- construir `RequestContext`
- proteger endpoint MCP

Done:

- request sin token falla
- request con token invalido falla
- request con token valido genera contexto autenticado

#### P0.4 Persistencia

- crear modelos `users`, `google_connections`, `oauth_states`, `audit_logs`
- crear migracion inicial
- crear session factory y repositorios

Done:

- migracion corre limpia
- se puede crear y leer usuario y conexion

#### P0.5 OAuth Google multiusuario

- implementar inicio de autorizacion
- guardar `state` y `code_verifier`
- callback
- intercambio de codigo por tokens
- persistencia cifrada de tokens
- refresh automatico
- desconexion o revocacion

Done:

- usuario puede vincular su cuenta
- tokens quedan guardados cifrados
- refresh funciona cuando expira el access token

#### P0.6 Tools MCP de auth

- `auth_google_begin`
- `auth_google_status`
- `auth_google_disconnect`

Done:

- el cliente puede iniciar el vinculo
- puede consultar estado
- puede desconectar su cuenta

#### P0.7 Capa comun Google

- reconstruccion de credenciales desde BD
- clientes Calendar, Tasks y Gmail por usuario
- manejo homogeneo de errores Google
- auditoria basica por tool call

Done:

- se puede obtener cliente Google valido para usuario autenticado
- errores del proveedor se normalizan

### P1 - Funcionalidad principal

#### P1.1 Calendar CRUD

- `calendar_list_calendars`
- `calendar_list_events`
- `calendar_get_event`
- `calendar_create_event`
- `calendar_update_event`
- `calendar_delete_event`

Done:

- CRUD basico completo
- validacion RFC3339 correcta
- aislamiento entre usuarios probado

#### P1.2 Tasks CRUD

- `tasks_list_tasklists`
- `tasks_create_tasklist`
- `tasks_update_tasklist`
- `tasks_delete_tasklist`
- `tasks_list_tasks`
- `tasks_create_task`
- `tasks_update_task`
- `tasks_complete_task`
- `tasks_delete_task`

Done:

- listas y tareas operan correctamente
- completar tarea funciona como abstraccion clara para el LLM

#### P1.3 Seguridad operativa minima

- audit logs por tool
- redaccion de argumentos sensibles
- rate limiting basico
- allow-list de tools activable por config

Done:

- cada tool call queda auditada
- no se registran secretos en logs
- throttling basico funciona

#### P1.4 Testing base

- unit tests para auth, OAuth, repositorios y validadores
- integration tests con mocks de Google
- pruebas de aislamiento multiusuario

Done:

- suite critica verde
- casos de auth y multiusuario cubiertos

### P2 - Cierre funcional y hardening

#### P2.1 Gmail v1

- `gmail_list_messages`
- `gmail_get_message`
- `gmail_list_threads`
- `gmail_create_draft`
- `gmail_update_draft`
- `gmail_delete_draft`
- `gmail_send_email`
- `gmail_delete_message`

Done:

- drafts funcionan
- envio funciona con MIME y base64url
- borrado se audita correctamente

#### P2.2 Normalizacion de respuestas

- outputs compactos para LLM
- paginacion consistente
- errores contractuales homogeneos

Done:

- tools responden con formatos previsibles y pequenos

#### P2.3 E2E MCP

- probar desde cliente MCP real
- validar handshake, auth, OAuth y CRUD

Done:

- flujo completo probado desde cliente compatible

## Calendario sugerido

- Dia 1-2: `P0.1`, `P0.2`
- Dia 2-3: `P0.3`
- Dia 3-4: `P0.4`
- Dia 4-6: `P0.5`, `P0.6`, `P0.7`
- Dia 6-8: `P1.1`
- Dia 8-9: `P1.2`
- Dia 9-10: `P1.3`, `P1.4`
- Dia 10-12: `P2.1`
- Dia 12-13: `P2.2`
- Dia 13-14: `P2.3`

## Definicion de done global

- servidor MCP remoto accesible por HTTP
- autenticacion por JWT funcionando
- usuario puede conectar exactamente una cuenta Google
- Calendar y Tasks con CRUD operativo
- Gmail con lectura, drafts, envio y borrado
- aislamiento entre usuarios verificado
- tokens cifrados en reposo
- logs y auditoria sin fuga de secretos
- pruebas base verdes

## Riesgos que pueden mover el sprint

- configuracion incorrecta de redirect URI en Google OAuth
- falta de claims confiables en el JWT del cliente
- refresh token no emitido por mala configuracion del consentimiento
- complejidad MIME en Gmail
- diferencias entre clientes MCP respecto a auth HTTP

## Mitigaciones

- probar OAuth temprano
- validar formato del JWT desde el inicio
- empezar Gmail por drafts antes del envio definitivo
- mantener outputs simples para agentes
- no ampliar alcance en v1
