# Release de seguridad en el homelab — 2026-10-01

## Versión publicada y desplegada

- Código: `4cdef42f2f82f49e3c8380e6a0d299bf37a0aaaa` en `JulioV93/mcp-google`, rama `main`.
- Docker Hub privado: `juliov93/mcp-google:sha-4cdef42f2f82f49e3c8380e6a0d299bf37a0aaaa`; plataforma `linux/amd64`.
- Imagen en producción: `juliov93/mcp-google@sha256:a39e079f2411fb804a0056ec159c36ff07d65bbaa56565c06e8dceb9acceeaf7`.
- Imagen anterior conservada: `juliov93/mcp-google@sha256:8cd41505cc10d2f7a0cbdf76f6ba8181290f4945664694f1c490bd2f67a5a6bf`.
- Servicio: `google-mcp-google-mcp-1`, en `/home/julio/docker/google-mcp/compose.yaml`.
- Endpoint público: https://google-mcp.vmmakeup.cl/mcp; salud: https://google-mcp.vmmakeup.cl/health.

La imagen contiene el commit de código indicado; este registro documental se publica después del despliegue. No se actualizó `latest` ni se eliminaron la imagen QA o la anterior.

## Evidencias

- 187 pruebas locales aprobadas, sin skips: SQLite y PostgreSQL desechables. Ruff, `pip check` y `git diff --check` aprobados.
- [GitHub Actions del código desplegado](https://github.com/JulioV93/mcp-google/actions/runs/36948033836): `success`, con lint, dependencias, pruebas PostgreSQL y construcción Docker.
- Auditoría `pip-audit` del lock, incluidas dependencias Linux: 102 paquetes, sin vulnerabilidades conocidas al ejecutar la comprobación. Esto no garantiza ausencia de vulnerabilidades desconocidas.
- Construcción amd64 limpia y prueba como UID 1000: migración desde cero, salud, JWT, aprobación y Origin. Dependencias de la imagen consistentes.
- Digest descargado en el homelab coincide con el publicado. Contenedor `healthy`, cero reinicios y `OOMKilled=false` durante la aceptación.
- HTTPS y loopback: JWT inválido devuelve 401; desconexión sin `approved_tools` devuelve 403; Origin no autorizado devuelve 403; initialize/list/ping MCP funcionan.
- Mismo subject, dos tenants de prueba y espacio sin tenant: sólo el espacio original conserva la conexión. Las identidades sintéticas de aceptación quedan sin conexión y con auditoría mínima.
- Host no autorizado devuelve 400. Body MCP mayor a 2 MiB devuelve 413.
- Una lectura real de Drive con `page_size=1` funcionó con la conexión existente; contenido y tokens no se imprimieron. No se probaron escrituras reales en Google.
- Cloudflared continúa activo; n8n `/healthz` responde 200 y Uptime Kuma conserva su redirección HTTP 302. No se cambiaron esos servicios ni las rutas del túnel.

## Migración y recuperación

Respaldo protegido: `/home/julio/docker/backups/google-mcp/20261002T010112Z-security`. Incluye SQLite, `.env` y Compose; directorio 700 y archivos 600. La copia se hizo con Google MCP detenido y la API backup de SQLite.

Se aplicó `20260314_120000` → `20261001_120000` antes de arrancar la imagen nueva. Se verificaron integridad y claves foráneas, y se conservaron los tres IDs originales, la conexión y sus tokens cifrados. No se rotaron la clave Fernet, la firma JWT ni las credenciales OAuth. Se retiró la columna de payload en texto plano y se actualizó la lista de aprobaciones, incluida la desconexión.

La restauración del respaldo se probó en un directorio temporal aislado: integridad, relaciones y revisión antigua correctas. El original se conserva protegido. Después de aceptar nuevas escrituras, inspeccionar efectos Google antes de restaurar operaciones antiguas; no ejecutar downgrade ni reactivar registros `unknown`.

## Recursos observados

- Límites conservados: 512 MiB, 0.5 CPU, UID/GID 1000:1000; puerto sólo `127.0.0.1:8000`.
- Durante aceptación: 170.1 MiB y 51.25% CPU; después: 136.8 MiB y 0.69% CPU. Son muestras puntuales en el Acer, no una comparación equivalente con la versión anterior ni una prueba prolongada.
- Host después de aceptación: 334 MiB de RAM disponible y 821 MiB de swap usada. No se añadieron contenedores permanentes.
- Medición determinista: cinco términos `all_terms` y un MIME usan una llamada en lugar de seis. Buffer para archivo simulado de 4 MiB: máximo 262144 bytes; pico de asignación 263210 bytes.

## Repetir verificaciones

En el homelab:

```sh
cd /home/julio/docker/google-mcp
docker compose ps
curl -fsS http://127.0.0.1:8000/health
docker compose exec -T google-mcp python -m alembic current
docker stats --no-stream
```

Consultar [seguridad y migración](21-seguridad-recursos-y-migracion.md) y [el runbook del homelab](../deploy/README.md) para JWT, backup y actualización. No imprimir `.env`, tokens o la configuración Compose expandida. La prueba real de escrituras requiere recursos de prueba autorizados; latencia y ahorro de cuota sostenidos no fueron medidos.
