# Tabla de reaccion del agente ante errores MCP

> Configuración actual: [permisos persistentes](23-permisos-persistentes.md).
> En `server_policy`, habilitar `read_write` una vez y conservar el JWT; `permission_denied`
> requiere un cambio administrativo. Las instrucciones de `approved_tools`,
> `approval_required` y las variables antiguas de aprobación de esta guía describen
> exclusivamente el modo heredado `jwt_claims`. La confirmación de operaciones es técnica.

## Objetivo

Esta tabla resume la reaccion recomendada del agente ante cada error estructurado del MCP.

Usa esta version cuando necesites una referencia rapida o una base mas facil de traducir a reglas automatizadas.

## Regla general

El agente debe leer los campos en este orden:

1. `error`
2. `retryable`
3. `category`
4. `metadata`
5. `detail`

No debe decidir solo por texto libre si ya existe `error`.

## Tabla principal

| error | category | retryable | que significa | que debe hacer el agente | que no debe hacer |
|---|---|---:|---|---|---|
| `validation_error` | `validation` | no | payload invalido, incompleto o fuera del schema | corregir argumentos y reintentar una sola vez con payload corregido | reintentar igual sin cambios |
| `unauthorized_client` | `auth` | no | JWT faltante, invalido o mal formado | corregir `Authorization`, renovar token o pedir credenciales validas | insistir con el mismo token |
| `approval_required` | `approval` | no | falta aprobacion humana para una tool sensible | pedir aprobacion y repetir solo con JWT que incluya `approved_tools` | buscar atajos o ejecutar otra accion destructiva |
| `origin_not_allowed` | `security` | no | el origen del request no esta permitido | revisar `ALLOWED_ORIGINS` y configuracion cliente-servidor | reintentar desde el mismo origen sin cambios |
| `rate_limited` | `rate_limit` | si | se excedio el limite por minuto local del MCP | esperar y reintentar con backoff, usando `metadata.retry_after_seconds` si existe | lanzar rafagas de reintentos |
| `google_consent_required` | `provider` | no | falta conexion Google activa o el consentimiento no es valido | iniciar/repetir OAuth, confirmar `auth_google_status` y reintentar luego | culpar al payload de la tool |
| `insufficient_scope` | `provider` | no | la cuenta Google no tiene permisos suficientes para esa accion | reconectar OAuth con scopes correctos y volver a intentar | reintentar en bucle con la misma conexion |
| `resource_not_found` | `provider` | no | el recurso ya no existe o el ID es incorrecto | verificar IDs, refrescar listados y corregir la referencia | seguir usando el mismo ID roto |
| `provider_temporary_error` | `provider` | si | fallo temporal del proveedor, timeout, 429 externo o 5xx | reintentar con backoff y limitar intentos | insistir indefinidamente |
| `provider_error` | `provider` | depende | fallo de proveedor no clasificado con precision | revisar `metadata.provider_status_code`, leer `detail` y decidir si parece auth/permisos/no encontrado/temporal | asumir automaticamente una sola causa |
| `configuration_error` | `internal` | no | el servidor esta mal configurado | detener flujo e informar problema de configuracion del MCP | reintentar automaticamente |
| `internal_error` | `internal` | no | bug o fallo interno del servidor MCP | escalar como bug del MCP, guardar `detail` y `metadata`, detener flujo | culpar al usuario o reintentar ciegamente |

## Tabla por categoria

| category | estrategia general del agente |
|---|---|
| `validation` | corregir input antes de repetir |
| `auth` | renovar o corregir autenticacion del cliente MCP |
| `approval` | pedir aprobacion humana o JWT con `approved_tools` |
| `security` | corregir configuracion de origen o host |
| `rate_limit` | esperar y reintentar con backoff |
| `provider` | distinguir entre consentimiento, scopes, recursos inexistentes y fallos temporales |
| `internal` | reportar bug o configuracion rota del servidor |

## Politica de reintento sugerida

| condicion | reintentar automaticamente |
|---|---|
| `retryable=true` y accion idempotente | si |
| `retryable=true` pero accion no claramente segura | con cautela o pedir confirmacion operativa |
| `retryable=false` | no |
| `approval_required` | no, hasta obtener aprobacion |
| `google_consent_required` | no, hasta completar OAuth |
| `insufficient_scope` | no, hasta reconectar con scopes nuevos |
| `configuration_error` | no |
| `internal_error` | no |

## Accion concreta por familia de tools

| tipo de tool | revisar primero si falla |
|---|---|
| Calendar | `calendar_id`, `event_id`, fechas RFC3339, `recurrence`, `reminders` |
| Tasks | `tasklist_id`, `task_id`, payload permitido por schema |
| Gmail | `message_id`, `draft_id`, email valido, scopes concedidos |
| Auth Google | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, redirect URI, estado de OAuth |

## Que reportar al usuario final

| dato | obligatorio |
|---|---|
| operacion que se intento ejecutar | si |
| `error` devuelto por el MCP | si |
| si es reintentable o no | si |
| siguiente accion recomendada | si |
| `metadata` relevante si existe | recomendado |

## Mensajes de ejemplo para el agente

### `approval_required`

```text
No pude completar la accion porque el MCP devolvio `approval_required`.
La operacion no es reintentable automaticamente.
Necesitas aprobar esta tool y volver a emitir el JWT con `approved_tools`.
```

### `google_consent_required`

```text
No pude continuar porque el MCP devolvio `google_consent_required`.
La cuenta Google no esta conectada o necesita reconexion.
Debes completar el flujo OAuth y luego reintentar.
```

### `insufficient_scope`

```text
No pude completar la accion porque el MCP devolvio `insufficient_scope`.
La cuenta Google esta conectada, pero no tiene permisos suficientes para esta operacion.
Debes reconectar OAuth con los scopes correctos antes de reintentar.
```

### `rate_limited`

```text
El MCP devolvio `rate_limited`.
La operacion es reintentable, asi que voy a esperar antes de volver a intentarlo.
```

### `internal_error`

```text
El MCP devolvio `internal_error`.
Esto parece un fallo interno del servidor, no un problema de tu instruccion.
Conviene escalarlo como bug del MCP con el detalle tecnico recibido.
```

## Referencias

- `docs/14-guia-reaccion-del-agente-ante-errores-mcp.md`
- `app/errors.py`
- `docs/13-guia-conectar-mcp-a-opencode.md`
