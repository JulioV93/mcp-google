# Validación de permisos persistentes — 2026-10-02

## Implementación verificada

- Versión: `0.2.0`; commit de código `02f43de08d01ae38ea01d2caab24a5b593f1a994`.
- Rama: `feature-gpt/persistent-user-permissions`; [PR #11](https://github.com/JulioV93/mcp-google/pull/11).
- Imagen amd64 publicada: `juliov93/mcp-google:sha-02f43de`.
- Digest publicado y desplegado: `sha256:96fae5aaec901a1e86a5a177a27d8e40e81d54b14f5ec5641457e1afe4e4848a`.
- La corrección posterior `03f4199` añade `pythonpath = ["."]` a pytest para que la
  invocación de CI encuentre `scripts`; no modifica la aplicación ni las migraciones
  incluidas en la imagen del commit de código.
- `pytest -q -rs -p no:cacheprovider`: 242 correctas; 4 omitidas porque no se configuró
  `TEST_POSTGRES_URL` para migración/concurrencia PostgreSQL.
- Ruff: todas las comprobaciones correctas.
- [GitHub CI](https://github.com/JulioV93/mcp-google/actions/runs/37086744755):
  **246 pruebas correctas, sin omisiones**, incluyendo migración y concurrencia
  PostgreSQL; Ruff, `pip check` y compilación Docker sin caché correctos.
- Prueba HTTP/MCP con JWT firmado real y proveedor Google simulado: crear, editar,
  preparar, revocar permiso, rechazar confirmación, reactivar permiso y confirmar
  usando el mismo token. Reutilizar la operación consumida se rechaza.
- Todas las escrituras/preparaciones del catálogo tienen pruebas parametrizadas
  de autorización. El catálogo coincide con las herramientas publicadas y sus anotaciones.
- Identidades/tenants aislados, denegaciones auditadas, administración local auditada,
  callback OAuth deshabilitado y autorización HTTP de desconexión verificados.

## Migración y reversión en Docker

Se ejecutó la imagen nueva, sin red, sobre una base SQLite ficticia creada en la
revisión anterior. La migración a `20261002_120000` conservó identidad, aplicó
`read_only` y pasó `integrity_check` y `foreign_key_check`.

La imagen anterior
`juliov93/mcp-google@sha256:9f5e479168994ed66c0bc06a3864bf233719e652d6d780acb239ed34de16659f`
inicializó su aplicación y leyó la identidad en esa base migrada, sin downgrade.
No se probaron escrituras Google mediante la imagen anterior.

Además, se ensayó la migración sobre una copia del respaldo real del homelab,
sin red. Las cinco identidades comenzaron en `read_only`; las filas y columnas
preexistentes de usuarios, conexiones Google, auditoría, OAuth y pendientes
permanecieron iguales. `integrity_check` devolvió `ok` y `foreign_key_check`, vacío.
La imagen anterior también inicializó su aplicación y leyó esa copia real migrada.

## Producción

Tras autorización explícita de publicación/despliegue, se respaldaron SQLite,
`.env` y Compose en almacenamiento local protegido: directorio 700 y archivos 600.
Se conservaron una copia inicial, la copia del ensayo aislado y el respaldo final
con el servicio detenido. Los respaldos, sus rutas y la configuración privada
no se publican en Git.

Producción quedó en revisión `20261002_120000`, versión `0.2.0` y
`AUTHORIZATION_MODE=server_policy`. Sólo la identidad acordada recibió
`read_write`; las otras cuatro identidades mantienen `read_only`. SQLite pasó
`integrity_check`. Se conservó el resto de la configuración, las claves y conexiones.
La comparación de huellas confirmó que el JWT desplegado es exactamente el configurado
en Hermes, sin emitir ni reemplazar tokens. El endpoint de salud respondió `0.2.0`.

El plugin GitHub permitió consultas, pero crear árbol/PR devolvió
`403 Resource not accessible by integration`. Se usaron Git/`gh` autenticados para
publicar la rama y crear la PR; Docker publicó la imagen por digest. No se cambiaron
los permisos de la integración de GitHub.

## Aceptación Google real

`scripts.access_acceptance` utilizó un cliente FastMCP independiente contra el
endpoint HTTPS y el archivo JWT preexistente. Creó una lista exclusiva de prueba,
creó una tarea, editó su título, preparó y confirmó su borrado, verificó la lista
vacía y preparó/confirmó la eliminación de esa misma lista. Todas las comprobaciones
pasaron y el recurso
de prueba quedó eliminado. No se tocó ninguna lista preexistente.

Hermes completó el mismo flujo por CLI con su configuración normal, sin cambiar
su política de aprobación ni su JWT, también en una lista nueva exclusiva de prueba.
Consultó permisos, creó lista y tarea, editó y verificó el título, revisó las vistas
previas y llamó ambas confirmaciones.
Verificó cero tareas tras borrar y eliminó la lista. No pidió otro sí conversacional.
La auditoría del servidor registra las llamadas exitosas de ese flujo.

La inicialización de esta ejecución CLI tardó varios minutos; durante ella hubo
un timeout transitorio de SSH. No se modificó Hermes para acelerar la prueba.
El MCP respondió saludable y el flujo concluyó. La latencia de inicialización del
cliente no demuestra por sí misma un problema de autorización del servidor.

La aceptación desde Telegram debe registrarse por separado: no confundir ejecución
CLI, pruebas con proveedor simulado y mensajes reales del canal Telegram. Seguir
[el runbook](23-permisos-persistentes.md).
No restaurar estos respaldos después de efectos Google: conservar pendientes actuales.
