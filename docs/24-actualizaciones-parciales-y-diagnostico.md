# Actualizaciones parciales y diagnóstico de Google MCP

## Contrato

`tasks_update_task` acepta uno o más campos de `task`, sin exigir `title`.
Los campos omitidos se conservan; `due: null` solicita quitar la fecha.
`notes: ""` vacía las notas. `title`, `notes` y `status` no admiten null explícito.
Las fechas enviadas en una actualización deben ser RFC3339 con zona horaria;
Google Tasks conserva el día y descarta la hora. La creación conserva sus requisitos.

```json
{"tasklist_id":"LIST_ID","task_id":"TASK_ID","task":{"due":"2026-11-14T00:00:00Z","notes":"Nueva nota"}}
```

```json
{"tasklist_id":"LIST_ID","task_id":"TASK_ID","task":{"due":null}}
```

`calendar_update_event` acepta uno o más campos de `event`, sin exigir título,
inicio o fin salvo que se estén modificando. `description: ""` y `location: ""`
vacían texto; `recurrence: []` quita recurrencia. Arrays enviados reemplazan los
anteriores. No se admiten campos desconocidos, un objeto vacío ni null explícito
para los campos superiores del evento. Los objetos de fecha conservan su validación.

```json
{"calendar_id":"primary","event_id":"EVENT_ID","event":{"description":"Nueva nota"}}
```

## Errores

La validación dentro de las herramientas de creación/actualización de Tasks y
Calendar devuelve `validation_error`, `category: validation`, `retryable: false`,
`expected_fields` y `metadata.validation_errors` (ruta y tipo, sin valores).
Las claves desconocidas se muestran como `<unknown_field>`. Corregir los campos
antes de reintentar. Los errores de protocolo/argumentos externos siguen bajo FastMCP.
Un error de herramienta no demuestra falta de conectividad. Un cliente que bloquea
llamadas durante un periodo de espera debe respetar ese periodo.

Las escrituras inciertas siguen devolviendo `google_operation_outcome_unknown`,
`retryable: false`, y pueden incluir `metadata.diagnostic_id`. Antes de preparar otra
operación se debe inspeccionar el recurso. Nunca repetir el mismo operation_id.
No existe reconciliación automática ni modificación de estados históricos.

El logger `app.google.diagnostics` registra antes de normalizar errores: identificador
aleatorio por llamada, herramienta, etapa, clase de excepción, código de aplicación y
estado/motivo del proveedor depurados cuando existen. Es visible con texto y LOG_JSON.
No registra mensajes originales, traceback, tokens, URLs, cabeceras, contenido ni IDs
personales. La auditoría de SQLite mantiene su esquema y error_code actuales.

Etapas Docs: `docs_read_document`, `docs_batch_update`, `docs_persist_confirmation`,
`docs_read_metadata`. Si falla guardar el estado del resultado: `persist_operation_outcome`.
Un fallo posterior a una confirmación persistida conserva la respuesta de confirmación
con `metadata_unavailable`. Los logs nuevos no reconstruyen excepciones antiguas perdidas.

## Verificación

Checks: `ruff check app tests scripts migrations --no-cache`, `python -m pip check`,
`pytest -q` y build Docker. CI proporciona PostgreSQL para las pruebas concurrentes;
las omisiones locales no constituyen evidencia PostgreSQL.

Tras desplegar el digest probado, ejecutar desde un entorno administrativo seguro:

```bash
python -m scripts.partial_update_acceptance \
  --url https://HOST_MCP/mcp \
  --token-file /ruta/privada/mcp.jwt \
  --report-file /ruta/privada/partial-update-acceptance.json
```

Requiere acceso read_write. Crea una lista/tarea, un evento sin asistentes en 2030 y
un Google Doc dedicados, con marcador aleatorio. Verifica actualización parcial,
eliminación de fecha y relectura, descripción de evento sin alterar horario, y append
exactamente una vez. Al pasar todas las comprobaciones, elimina la lista/evento de
prueba y mueve el Doc de prueba a la papelera mediante preparación/confirmación.
No modifica recursos previos. stdout contiene únicamente resultados booleanos.
El reporte privado (modo 600) conserva IDs y etapa para inspección si falla.

Ante error, el script se detiene: no reintenta escrituras ni elimina automáticamente
recursos, pues el efecto externo puede ser incierto. Revisar el reporte y el recurso
antes de limpiar o repetir. No simular fallos de transporte en producción.

## Entrega, despliegue y rollback

La entrega requiere PR y CI verde. Construir fuera del homelab para linux/amd64 y
publicar sha-<commit> en el registro existente; registrar el digest devuelto.
No añadir dependencias, scopes, infraestructura ni migraciones para esta corrección.

Seguir deploy/README.md: comprobar capacidad y digest vigente, respaldar SQLite,
.env y compose en almacenamiento protegido, conservar claves y la imagen anterior.
Desplegar manualmente el digest autorizado y comprobar health, autenticación,
initialize/list/ping y aceptación funcional. Si hay regresión, restaurar el digest
anterior; esta corrección no cambia el esquema de datos.

Distinguir evidencia local, CI/build y Google real. Un build exitoso no demuestra
que Google haya quitado una fecha ni que el cliente haya mostrado el error estructurado.
No publicar IDs de recursos, identidades, reportes privados ni contenido de documentos.
