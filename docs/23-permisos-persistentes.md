# Permisos persistentes y acciones con el mismo JWT

## Modelo

`AUTHORIZATION_MODE=server_policy` separa autenticación y autorización. El JWT válido
identifica `(tenant_id, sub)` y la tabla `users` guarda `access_profile`:

| Perfil | Acceso |
|---|---|
| `read_only` | Consultas, permisos e inicio/completado OAuth |
| `read_write` | Lo anterior, preparaciones, escrituras y desconexión |
| `disabled` | Acceso autenticado y completado OAuth bloqueados |

Usuarios nuevos y migrados comienzan en `read_only`. Cada llamada consulta la base;
retirar permisos bloquea la siguiente llamada, también entre preparar y confirmar.
No hay autoelevación MCP/HTTP. Los agentes que comparten identidad comparten permisos.

`auth_get_permissions` devuelve `authorization_mode`, `access_profile`, `allowed_tools`
y `confirmation_policy=explicit_user_request`. Los permisos Google siguen dependiendo
del consentimiento OAuth y sus scopes; habilitar el perfil no amplía esos scopes.

## Administración

Ejecutar dentro del contenedor para usar el mismo entorno y SQLite persistente:

```sh
docker compose exec -T google-mcp python -m scripts.homelab_credentials get-access --subject IDENTIDAD
docker compose exec -T google-mcp python -m scripts.homelab_credentials set-access --subject IDENTIDAD --profile read_write
```

Añadir `--tenant-id TENANT` a ambos comandos si el JWT ya incluye tenant.
`set-access` provisiona identidades nuevas y guarda perfil y auditoría en una transacción.
Para revocar escrituras usar `read_only`; para bloquear la identidad usar `disabled`.
No se necesitan claves de firma para estos comandos; nunca imprimir el `.env` ni tokens.

## Contrato para cualquier agente

Crear/editar se ejecuta directamente. Para borrar/enviar/compartir/sobrescribir, las
herramientas que ya preparaban operaciones siguen devolviendo la vista previa:

```json
{
  "operation_id": "...",
  "requires_confirmation": true,
  "confirmation_tool": "tasks_confirm_delete_task",
  "confirmation_arguments": {"operation_id": "..."}
}
```

Una solicitud explícita con objetivo y alcance claros permite revisar y ejecutar ese
paso técnico con el mismo JWT, sin otro sí impuesto por el servidor. Ante ambigüedad
o un alcance diferente, el agente pide aclaración. El MCP no demuestra consentimiento
humano a partir de la llamada; el cliente interpreta el mensaje y mantiene su política.
No se exige `elicitation` ni una UI especial. Las anotaciones describen efectos,
pero nunca conceden permisos. Las preparaciones almacenan pendientes y por eso no
se anuncian como operaciones estrictamente de lectura ni idempotentes.

`permission_denied` es 403, no reintentable, categoría `authorization`: necesita una
acción administrativa, no otro sí ni reemplazo del token. `approval_required` sólo
pertenece al modo heredado. Una escritura incierta no se reenvía automáticamente.

## Migración y aceptación

1. Detener el servicio y respaldar SQLite con su API de backup, `.env` y Compose.
   Proteger directorio 700 y archivos 600. Registrar imagen anterior y revisión.
2. Identificar el `sub`/tenant actuales desde la configuración protegida del cliente,
   sin imprimir el bearer ni cambiarlo. Preparar una imagen inmutable por digest.
3. Aplicar `alembic upgrade head`: revisión `20261002_120000`, aditiva, perfiles
   `read_only`, mismos IDs, conexiones, cifrado y pendientes.
4. Habilitar sólo la identidad acordada con `set-access`; establecer
   `AUTHORIZATION_MODE=server_policy` en el `.env` y recrear el servicio.
5. Consultar permisos y ejecutar `scripts.access_acceptance` con el JWT existente.
   Crea una lista identificable, una tarea, la edita y borra, luego elimina la lista.
   Si hay resultado incierto, detenerse e inspeccionar Google antes de limpiar/repetir.
6. Desde Hermes/Telegram repetir crear, editar y borrar en recursos de prueba con
   el mismo JWT. Registrar resultado aparte de la comprobación del segundo cliente.

Sin `AUTHORIZATION_MODE`, se conserva `jwt_claims`. En ese modo siguen vigentes
`REQUIRE_EXPLICIT_APPROVAL` y `APPROVAL_REQUIRED_TOOLS`. En `server_policy` se ignoran
con advertencia. El perfil `disabled` bloquea ambos modos. Cambiar a `jwt_claims`
restaura la autorización heredada y puede volver a limitar las escrituras de Hermes.
No altera los vencimientos de JWT ni rota claves OAuth/Fernet/firma.

## Reversión

Ensayar en una copia aislada: migrar y verificar que la imagen anterior funciona
con la columna adicional y configuración `jwt_claims`, sin ejecutar downgrade.
La reversión de modo puede hacerse con la misma imagen nueva, que conserva el bloqueo
`disabled`. Una imagen anterior desconoce ese perfil: no volver a ella si hay
identidades deshabilitadas sin establecer previamente un bloqueo equivalente.
No restaurar una base anterior después de escrituras Google, porque podría reactivar
pendientes consumidos o inciertos. Mantener el estado actual y verificar efectos externos.
