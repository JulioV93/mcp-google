# Guia de reaccion del agente ante errores MCP

## Objetivo

Esta guia explica como debe reaccionar un agente cuando este servidor MCP devuelve un error estructurado.

El objetivo no es solo mostrar el error, sino decidir correctamente si debe:

- corregir el input
- pedir aprobacion humana
- reconectar OAuth Google
- reintentar mas tarde
- escalar como bug interno

## Forma del error

Las tools MCP y varios endpoints HTTP devuelven errores con esta estructura:

```json
{
  "error": "insufficient_scope",
  "detail": "Request had insufficient authentication scopes.",
  "retryable": false,
  "category": "provider",
  "metadata": {
    "provider": "google",
    "provider_status_code": 403
  }
}
```

Campos:

- `error`: codigo estable para automatizacion
- `detail`: mensaje legible para depuracion
- `retryable`: indica si conviene reintentar automaticamente
- `category`: clasificacion general del error
- `metadata`: datos adicionales utiles en algunos casos

## Regla principal para el agente

Antes de decidir, el agente debe seguir este orden:

1. leer `error`
2. leer `retryable`
3. leer `category`
4. usar `metadata` si existe
5. solo despues usar `detail` como ayuda humana

No se debe tomar decisiones solo por texto libre cuando ya existe `error`.

## Reaccion por categoria

### `validation`

Significa que el payload enviado no cumple el contrato esperado.

El agente debe:

- revisar argumentos
- corregir formato o campos
- volver a intentar solo con payload corregido

El agente no debe:

- reintentar exactamente lo mismo
- culpar a Google o al servidor

### `auth`

Significa que el cliente MCP no se autentico correctamente.

El agente debe:

- verificar el bearer token
- comprobar que el cliente envia `Authorization: Bearer <token>`
- si es un entorno real, renovar o solicitar un JWT valido

El agente no debe:

- reintentar sin cambiar el token

### `approval`

Significa que la tool requiere aprobacion humana.

El agente debe:

- detener la ejecucion de esa accion sensible
- solicitar aprobacion a la plataforma o al usuario
- reintentar solo cuando exista un JWT con `approved_tools`

El agente no debe:

- intentar una alternativa destructiva sin aprobacion

### `security`

Significa que el request fue bloqueado por politica de seguridad, por ejemplo `Origin` no permitido.

El agente debe:

- revisar configuracion cliente-servidor
- validar `ALLOWED_ORIGINS` y `ALLOWED_HOSTS` cuando aplique

El agente no debe:

- insistir con el mismo origen si sigue bloqueado

### `rate_limit`

Significa que el servidor local del MCP esta limitando frecuencia.

El agente debe:

- esperar antes de reintentar
- usar backoff si ejecuta varias llamadas seguidas
- consultar `metadata.retry_after_seconds` si existe

El agente no debe:

- lanzar una rafaga de reintentos inmediatos

### `provider`

Significa que el problema viene de Google o de la integracion con Google.

El agente debe distinguir por `error` especifico.

### `internal`

Significa bug o fallo interno del servidor.

El agente debe:

- detener el flujo actual
- reportar el problema como error interno del MCP
- incluir `error`, `detail` y `metadata` en el reporte

El agente no debe:

- culpar al usuario
- seguir reintentando sin evidencia de recuperacion

## Reaccion por codigo exacto

### `validation_error`

Que significa:

- payload incompleto
- formato invalido
- campos no soportados
- fechas o IDs mal enviados

Que debe hacer el agente:

1. revisar argumentos
2. corregir el payload
3. reintentar una sola vez con el payload corregido

Ejemplos:

- `calendar_create_event` sin `start`
- `gmail_create_draft` sin `subject`
- callback OAuth sin `state` o `code`

### `unauthorized_client`

Que significa:

- falta header `Authorization`
- JWT invalido
- JWT expirado o mal formado

Que debe hacer el agente:

1. verificar el bearer token
2. pedir un token valido o renovar sesion
3. reintentar solo despues de corregir auth

### `approval_required`

Que significa:

- la tool fue marcada como sensible
- el JWT no trae `approved_tools` con ese nombre

Que debe hacer el agente:

1. explicar que falta aprobacion humana
2. pedir aprobacion a la plataforma o al usuario
3. repetir la llamada solo con JWT actualizado

Ejemplos tipicos:

- `gmail_send_email`
- `gmail_delete_message`
- `calendar_delete_event`

### `origin_not_allowed`

Que significa:

- el request al endpoint MCP trae un `Origin` no incluido en `ALLOWED_ORIGINS`

Que debe hacer el agente:

1. informar que es un problema de configuracion
2. indicar el origen usado
3. pedir que se agregue ese origen al servidor si corresponde

### `rate_limited`

Que significa:

- el sujeto actual supero el limite configurado por minuto

Que debe hacer el agente:

1. esperar
2. reintentar con backoff
3. agrupar llamadas si estaba haciendo demasiadas operaciones separadas

Politica recomendada:

- primer reintento: esperar 5 a 15 segundos
- segundo reintento: esperar mas
- no insistir indefinidamente

### `google_consent_required`

Que significa:

- no hay conexion Google activa
- falta consentimiento
- el token Google no es utilizable
- el ID token no fue devuelto o fue invalido

Que debe hacer el agente:

1. ejecutar `auth_google_begin` si corresponde
2. pedir al usuario que complete OAuth en navegador
3. volver a comprobar `auth_google_status`
4. repetir la tool original solo si `connected=true`

### `insufficient_scope`

Que significa:

- la cuenta Google esta conectada, pero faltan permisos para esa accion

Que debe hacer el agente:

1. explicar que la cuenta necesita scopes adicionales
2. pedir reconexion OAuth con los permisos correctos
3. reintentar solo despues de reconectar

Ejemplos:

- usar una tool Gmail sin `gmail.modify`
- intentar una accion no cubierta por los scopes actuales

### `resource_not_found`

Que significa:

- el recurso de Google ya no existe o el ID es invalido

Que debe hacer el agente:

1. verificar el ID usado
2. si el recurso venia de una llamada anterior, refrescar el listado
3. no reintentar en bucle con el mismo ID

Ejemplos:

- `event_id` inexistente
- `message_id` inexistente
- `task_id` borrado antes de usarlo

### `provider_temporary_error`

Que significa:

- error transitorio del proveedor
- timeout
- 429 externo
- 5xx de Google

Que debe hacer el agente:

1. reintentar con backoff exponencial
2. limitar el numero de reintentos
3. si sigue fallando, informar indisponibilidad temporal

Politica recomendada:

- intento 1: inmediato solo si la operacion es idempotente
- intento 2: esperar unos segundos
- intento 3: esperar mas y luego abortar

### `provider_error`

Que significa:

- error del proveedor no clasificado con mas precision

Que debe hacer el agente:

1. revisar `metadata.provider_status_code`
2. leer `detail`
3. decidir si parece auth, permisos, no encontrado o temporal
4. si no puede clasificarlo, reportarlo como error de integracion

### `configuration_error`

Que significa:

- el servidor esta mal configurado
- por ejemplo, faltan `GOOGLE_CLIENT_ID` o `GOOGLE_CLIENT_SECRET`

Que debe hacer el agente:

1. detener el flujo
2. informar que el problema es de configuracion del servidor
3. no reintentar automaticamente

### `internal_error`

Que significa:

- bug del MCP
- invariante rota
- error inesperado del servidor

Que debe hacer el agente:

1. detener la accion actual
2. informar error interno del MCP
3. guardar `detail` y `metadata` para soporte
4. no reintentar automaticamente salvo que el operador lo indique

## Politica de reintentos recomendada

### Reintentar automaticamente

Solo si:

- `retryable=true`
- la accion es segura o idempotente
- no se trata de aprobacion, auth o configuracion

Casos tipicos:

- `rate_limited`
- `provider_temporary_error`

### No reintentar automaticamente

Si el error es:

- `validation_error`
- `unauthorized_client`
- `approval_required`
- `google_consent_required`
- `insufficient_scope`
- `configuration_error`
- `internal_error`

## Guia especifica por tipo de accion

### Si la tool era de Calendar

Revisar especialmente:

- formato RFC3339 en fechas
- `calendar_id`
- `event_id`
- `recurrence`
- `reminders`

### Si la tool era de Tasks

Revisar especialmente:

- `tasklist_id`
- `task_id`
- payload permitido por schema

### Si la tool era de Gmail

Revisar especialmente:

- scopes concedidos
- `message_id` o `draft_id`
- direcciones de email validas

## Que debe reportar el agente al usuario

Siempre que falle una tool, el agente deberia incluir:

1. que operacion intento ejecutar
2. el `error` recibido
3. si es reintentable o no
4. la accion recomendada para destrabarlo

Ejemplo bueno:

```text
No pude enviar el correo porque el MCP devolvio `approval_required`.
La accion no es reintentable automaticamente.
Necesitas aprobar la tool `gmail_send_email` y volver a emitir el JWT con `approved_tools`.
```

## Checklist minima para implementar en un agente

- [ ] leer y parsear `error`
- [ ] usar `retryable` para decidir reintento
- [ ] usar `category` para clasificar el problema
- [ ] mirar `metadata` cuando exista
- [ ] no decidir solo por `detail`
- [ ] no reintentar automaticamente errores no reintentables
- [ ] pedir OAuth o aprobacion cuando el error lo indique

## Referencias utiles

- `app/errors.py`
- `docs/02-autenticacion-y-seguridad.md`
- `docs/08-validacion-manual-google-real.md`
- `docs/13-guia-conectar-mcp-a-opencode.md`
- `docs/15-tabla-reaccion-agente-errores-mcp.md`
- `docs/16-system-prompt-opencode-errores-mcp.md`
- `docs/17-reglas-automaticas-agente-errores-mcp.yaml`
