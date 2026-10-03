# Validación de permisos persistentes — 2026-10-02

## Implementación verificada

- Versión: `0.2.0`; commit de código `02f43de08d01ae38ea01d2caab24a5b593f1a994`.
- Rama local: `feature-gpt/persistent-user-permissions`.
- Imagen local amd64: `juliov93/mcp-google:sha-02f43de`.
- Digest de imagen local: `sha256:96fae5aaec901a1e86a5a177a27d8e40e81d54b14f5ec5641457e1afe4e4848a`.
  Todavía no es una referencia publicada del registro.
- `pytest -q -rs -p no:cacheprovider`: 242 correctas; 4 omitidas porque no se configuró
  `TEST_POSTGRES_URL` para migración/concurrencia PostgreSQL.
- Ruff: todas las comprobaciones correctas.
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

## Producción y pasos pendientes

Comprobado por SSH: el homelab continúa saludable en `0.1.0`, con la imagen anterior.
No se modificaron SQLite de producción, configuración del MCP, permisos ni JWT.
La identidad configurada de Hermes es `julio-homelab`, sin tenant ni vencimiento.
Se inspeccionaron sólo claims seleccionados; no se imprimió ni copió el bearer.

La revisión automática rechazó `git push` y `docker push` porque exige autorización
explícita para los destinos y contenidos publicados. GitHub `JulioV93/mcp-google`
es público y la cuenta tiene permisos ADMIN. La imagen nueva permanece local.

Después de autorizar esos destinos: publicar la rama y la imagen, confirmar digest
del registro, respaldar SQLite/configuración, ensayar migración en copia real aislada,
aplicar migración, habilitar únicamente `julio-homelab`, activar `server_policy`,
y recrear el servicio conservando claves, OAuth y JWT. Seguir
[el runbook](23-permisos-persistentes.md).

La aceptación real con Google, el segundo cliente y Hermes/Telegram está pendiente.
No confundir las pruebas HTTP con proveedores simulados con aceptación Google real.
