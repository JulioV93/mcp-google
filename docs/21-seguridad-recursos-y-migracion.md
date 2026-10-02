# Seguridad, recursos y migración — 2026-10-01

Esta versión requiere migración antes de iniciar. No publicar la imagen ni ejecutar estos pasos en producción sin revisar el diff y las pruebas.

## Contrato y compatibilidad

- Identidad: `(tenant_id, sub)`. Ausencia de `tenant_id` usa un espacio independiente; un tenant presente vacío, no string o mayor a 255 caracteres se rechaza. Se mantienen IDs y conexiones; un tenant almacenado no se cambia al recibir otro JWT. Antes de migrar, revisar `SELECT id, external_subject, tenant_id FROM users ORDER BY id` contra las identidades emitidas, sin imprimir tokens.
- Producción exige aprobaciones para todas las herramientas que escriben, incluidas confirmaciones y desconexión HTTP/MCP. Preparar una operación, iniciar OAuth o leer no necesita aprobación adicional. `approved_tools` es autorización administrativa por herramienta, no prueba de consentimiento humano ni aprobación por payload.
- `operation_id` se reclama atómicamente antes del proveedor. Estados: `pending`, `executing`, `confirmed`, `failed`, `unknown`, `expired`, `cancelled`. Un resultado incierto retorna `google_operation_outcome_unknown`, sin reintento automático. Inspeccionar Google antes de preparar otra operación. No se promete exactamente una vez entre la base y Google.
- Si falla la consulta de metadata después de una escritura confirmada, la respuesta conserva `confirmed=true` y agrega `metadata_unavailable=true`. No repetir la escritura por falta de metadata.
- OAuth state se consume antes del intercambio: un fallo requiere un enlace nuevo. Cambiar de cuenta no conserva el refresh token anterior.
- Errores Google exponen códigos y estado, no mensajes libres del proveedor que puedan repetir contenido o credenciales. JWKS caído retorna 503 y tokens inválidos 401.
- Límite HTTP MCP: 2 MiB (`MCP_BODY_LIMIT_BYTES`), también sin Content-Length. Drive inline: 256 KiB (`DRIVE_INLINE_CONTENT_LIMIT_BYTES`), chunks de 64 KiB y Base64 estricto. Timeout Google: 30 s (`GOOGLE_API_TIMEOUT_SECONDS`); JWKS: 10 s.
- Páginas: Calendar 1–2500, Gmail 1–500, Tasks 1–100. Drive advanced: hasta 8 términos y 8 MIME types, sin consultas duplicadas y con presupuesto de 16 consultas. `query_used.incomplete=true` indica presupuesto agotado; no interpretar ausencia de resultados como búsqueda exhaustiva.
- Payloads pendientes cifrados con la clave Fernet existente. Contenido y nombres sensibles se limpian al terminar o vencer. Auditoría por campos permitidos, sin contenido ni destinatarios; retención de 30 días. Limpieza al arrancar y cada 60 s en lotes de 500; grandes atrasos pueden requerir varios ciclos. Al arrancar se convierten ejecuciones interrumpidas en `unknown`.
- Un worker. El rate limiter es por proceso; varias réplicas requieren un límite compartido y recuperación coordinada de operaciones. No arrancar dos versiones sobre la misma base. Transportes y credenciales se reutilizan solo dentro de una herramienta y se cierran al terminar.

## Validación local

Desde la raíz, con Python 3.13:

```sh
python -m pip install -c requirements.lock hatchling
python -m pip install --no-build-isolation -c requirements.lock '.[dev]'
ruff check app tests scripts migrations --no-cache
python -m pip check
python -m pytest -q
python -m scripts.resource_check
```

`requirements.lock` fija las versiones del entorno probado, más dependencias de Linux verificadas mediante resolución sin instalación. No incluye una actualización mayor. CI ejecuta las mismas comprobaciones, la migración PostgreSQL y la construcción Docker.

Para validar PostgreSQL usar solo una base desechable, nunca la URL productiva:

```sh
TEST_POSTGRES_URL=postgresql+psycopg://test:test@localhost:5432/mcp_google_test python -m pytest -q
```

La prueba crea y elimina un schema con nombre aleatorio. Sin `TEST_POSTGRES_URL`, se informa un skip para PostgreSQL. El caso SQLite siempre se ejecuta. Esta misma URL habilita también las pruebas de concurrencia PostgreSQL.

```sh
docker build --no-cache -t mcp-google:security-check .
```

Estas pruebas no envían correo ni escriben en Google. La medición local compara el caso de cinco términos y un MIME: seis consultas equivalentes en el código anterior frente a una actual. Mide el buffer de un archivo simulado de 4 MiB, no el RSS del proceso ni latencia o cuotas reales de Google.

## Evidencia de aceptación local

- 187 pruebas aprobadas, incluidas las 141 existentes; SQLite y PostgreSQL reales temporales, sin skips. Incluye migración, concurrencia, transporte HTTP MCP e identidad, interrupciones, privacidad y event loop.
- Ruff, `pip check` y `git diff --check` sin errores. Docker construido sin caché sobre Python 3.13 fijado por digest; dependencias y backend de construcción fijados.
- Caso reproducible de Drive `all_terms`: 6 consultas anteriores frente a 1 actual. Archivo simulado de 4 MiB: buffer detenido en 262144 bytes y pico de asignación del buffer de 263210 bytes. Ejecutar `python -m scripts.resource_check` para repetirlo.
- Imagen validada como UID 1000: migración desde cero, salud, JWT inválido, estado desconectado, aprobaciones y rechazo de Origin en MCP. Sin credenciales reales ni escrituras Google.
- PostgreSQL temporal retirado al terminar. No se aplicaron migraciones productivas ni se publicaron imágenes. Latencia, RSS total y ahorro de cuota en infraestructura real siguen sin medir.

## Preparar JWT administrativos

La herramienta no imprime credenciales y crea el archivo con permiso 0600. Sin `--approve-tool`, el JWT es de lectura en producción.

```sh
python -m scripts.homelab_credentials --env .env issue-token --subject usuario-123 --tenant-id empresa-a --output usuario.token
python -m scripts.homelab_credentials --env .env issue-token --subject usuario-123 --tenant-id empresa-a --approve-tool gmail_confirm_send_email --output envio-autorizado.token
```

Actualizar las variables existentes siguiendo `deploy/.env.mcp-google.example`; una lista antigua `APPROVAL_REQUIRED_TOOLS` incompleta impedirá arrancar en producción. No copiar claves nuevas sobre las existentes.

## Aplicación posterior de la migración

1. Detener tráfico y el servidor. Comprobar un único worker y respaldar la base y `TOKEN_ENCRYPTION_KEY` con acceso restringido. SQLite: hacer el respaldo con el proceso detenido; PostgreSQL: usar un respaldo consistente.
2. Revisar la correspondencia de tenants actuales. No se intenta reconstruir tenants sobrescritos por versiones previas.
3. Instalar el código y versiones fijadas en un entorno aislado. Verificar que la misma clave Fernet está disponible y ejecutar:

```sh
python -m alembic upgrade head
python -m alembic current
```

La revisión esperada es `20261001_120000`. Cifra payloads válidos, limpia pendientes vencidos y auditorías históricas, y retira la columna en texto plano. La migración modifica datos y requiere la clave; no usar SQL offline.

4. Arrancar la imagen nueva identificada por digest y validar `/health`, rechazo de JWT inválido, aislamiento tenant y una lectura Google con un JWT autorizado. Las escrituras reales solo se prueban con recursos de prueba autorizados.
5. Backups y páginas SQLite antiguas pueden conservar contenido previo aunque ya no esté en las columnas activas. Aplicar retención y protección de backups; no publicar ni compartir copias históricas.

Si la migración falla: detener el proceso, restaurar el backup protegido y la imagen anterior. `downgrade` está bloqueado para evitar volver a texto plano o mezclar tenants. Si ya hubo escrituras externas, inspeccionar y conciliar efectos Google antes de restaurar operaciones antiguas. Nunca convertir `unknown` a `pending` automáticamente.
