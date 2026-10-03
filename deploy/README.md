# Google MCP en jm-homelab

## Arquitectura y límites

Acer Aspire 5250, Debian 13 amd64, usuario `julio`, 2 GB de RAM.
La información del hardware debe contrastarse por SSH antes del despliegue.
UID/GID 1000:1000 confirmados por SSH; el compose ejecuta el proceso con esos IDs.
Un contenedor MCP con SQLite; sin PostgreSQL adicional, proxy ni otro túnel.
Uptime Kuma y Hermes permanecen como servicios independientes.

```text
Internet HTTPS -> Cloudflare -> túnel EXISTENTE -> Google MCP:8000 -> Google APIs
                  google-mcp.vmmakeup.cl          SQLite persistente
```

El compose `docker-compose.prod.yml` se copia al servidor como
`/home/julio/docker/google-mcp/compose.yaml`. La plantilla es
`deploy/.env.mcp-google.example`, copiada como `.env`. Persistir `./data:/app/data`.
Puerto publicado exclusivamente en `127.0.0.1:8000`; restart `unless-stopped`,
512 MB, 0.5 CPU, logs con rotación de 10 MB y 3 archivos. Ajustar los límites
sólo según mediciones; comprobar que los servicios existentes siguen respondiendo.

## Imagen

Repositorio privado `juliov93/mcp-google`. Referencia QA: `oauth-callback-fix`.
La versión Home Lab se construye fuera del Acer, para `linux/amd64`, desde `main`
consolidado y probado. Publicar `sha-<commit>` y registrar digest. Desplegar
`MCP_GOOGLE_IMAGE=juliov93/mcp-google@sha256:<digest>`, sin usar `latest`.
No borrar la imagen QA ni la versión anterior durante la limpieza de ramas.

## Secretos e identidad

El `.env` real y `data/` nunca se versionan. `.env` debe tener modo 600 y el
directorio de despliegue/datos modo 700. Los tokens Google se cifran en SQLite;
la base sigue conteniendo otros datos privados y debe protegerse y respaldarse.

- `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`: cliente web del proyecto GCP propio.
- `TOKEN_ENCRYPTION_KEY`: clave Fernet generada localmente. Mantenerla al actualizar.
- `JWT_SHARED_SECRET`: clave local de firma; sólo para el administrador.
- JWT del MCP: distinto del token Google; una identidad `sub` estable por persona.
- `JWT_TEST_MODE=false`, algoritmo HS256, audiencia `google-mcp-server`,
  emisor `urn:jm-homelab:google-mcp`. No existe un endpoint público emisor de JWT.

La utilidad `scripts/homelab_credentials.py` permite inicializar las claves que
faltan y emitir JWT en archivos 600. Por defecto duran una hora; con
`JWT_ALLOW_NON_EXPIRING_TOKENS=true`, se emiten y aceptan sin vencimiento. No rota
claves existentes ni imprime tokens. Sólo incluye `approved_tools` si se solicita
mediante `--approve-tool`. El smoke test admite `--token-file`
para evitar pasar credenciales en argumentos visibles de procesos.

### JWT sin vencimiento durante la marcha blanca

La plantilla de despliegue activa `JWT_ALLOW_NON_EXPIRING_TOKENS=true`.
Para un despliegue existente, añadir esa variable al `.env` y recrear el servicio
para que cargue la configuración:

```bash
docker compose up -d --force-recreate google-mcp
```

En el entorno administrativo con las dependencias instaladas, emitir un token
con el mismo `sub` que ya usa la persona (archivo de salida nuevo):

```bash
python -m scripts.homelab_credentials --env /ruta/al/.env issue-token \
  --subject julio --output /ruta/privada/julio-mcp.jwt
```

Usar ese JWT como bearer en la configuración de Hermes u otro cliente MCP.
Sólo hay que reemplazarlo una vez. No entregar al cliente `JWT_SHARED_SECRET`.
Los JWT existentes conservan su vencimiento; activar la opción no los modifica.
Incluso con la opción activa, un JWT que incluya `exp` vencido se rechaza.

No hay revocación individual: cambiar la clave de firma invalida todos los JWT
firmados con ella. Desactivar la opción rechaza todos los JWT sin vencimiento y
vuelve a emitir tokens de una hora. Los permisos de herramientas y la renovación
o revocación de las credenciales Google mantienen su comportamiento actual.

No copiar access/refresh tokens de Google al `.env`. Se obtienen con consentimiento.
No mostrar secretos, estados OAuth, URLs completas de callback, variables reales,
configuración Docker expandida o comandos del túnel que contengan su token.

## Scopes y herramientas

Se conservan los scopes de `app/config.py`: calendar, tasks, gmail.readonly,
gmail.compose, gmail.modify, drive, documents, spreadsheets, openid, userinfo.email
 y userinfo.profile. Los prefijos de los scopes Google son
`https://www.googleapis.com/auth/`, salvo `openid`. No se añaden scopes de Contacts.

| Servicio | Escrituras relevantes |
|---|---|
| Gmail | Crear/modificar/borrar borradores; envío con preparación/confirmación; mensajes a papelera |
| Calendar | Crear/modificar eventos; eliminar con preparación/confirmación |
| Tasks | Crear/modificar listas y tareas, completar; eliminar con preparación/confirmación |
| Drive | Crear carpetas/Docs/Sheets/Slides/atajos, metadata, mover, cargar, escribir, compartir, revocar y borrar |

Drive admite borrado permanente tras confirmación. Contacts no está implementado.
La plantilla usa `AUTHORIZATION_MODE=server_policy`: habilitar una vez el perfil
`read_write` del usuario con `set-access`, conservando su JWT y conexión Google.
La petición explícita puede autorizar el flujo de preparación/confirmación técnica.
Consultar [permisos persistentes](../docs/23-permisos-persistentes.md) para migración,
aceptación de escrituras sobre recursos de prueba y reversión. Los despliegues sin
`AUTHORIZATION_MODE` conservan `jwt_claims` y las comprobaciones históricas.

## GCP: recorrido funcional

1. Abrir https://console.cloud.google.com/ -> selector de proyecto -> Nuevo proyecto.
   Nombre `Google MCP Home Lab`. Seleccionarlo y registrar ID; no modificar QA.
2. APIs y servicios -> Biblioteca: habilitar Calendar, Tasks, Gmail, Drive, Docs,
   Sheets y Slides. No habilitar People API.
3. Google Auth Platform -> Branding -> Get started: nombre `Google MCP Home Lab`,
   correo de soporte y contacto, audiencia External.
4. Audience: empezar en Testing y agregar las cuentas conocidas de prueba.
5. Data Access -> Add or remove scopes: declarar exactamente los scopes anteriores.
   Revisar las categorías sensibles/restringidas; no ampliar permisos.
6. Clients -> Create client -> Web application. Nombre `Google MCP Home Lab Web`.
   Authorized redirect URIs:
   `https://google-mcp.vmmakeup.cl/oauth/google/callback` (sin barra final).
   No se necesitan orígenes JavaScript para este flujo de servidor.
7. Guardar Client ID y Client Secret localmente e introducirlos en el `.env`
   del servidor. Nunca pegarlos en un chat ni versionarlos.
8. Después de publicar el hostname, iniciar `/oauth/google/start` con JWT de la
   identidad correspondiente. Guardar su enlace de autorización en un archivo
   protegido, abrirlo en el navegador habitual, seleccionar cuenta y consentir.
   No abrir `/oauth/google/start` sin Bearer: esa ruta no es un formulario de login.
9. Ver la página HTML de resultado. `/oauth/google/status` conserva JSON autenticado.
   Comprobar una lectura y repetir con otra identidad para verificar aislamiento.
10. Después de probar: Audience -> Publish app / In production, para el uso reducido
    por personas conocidas. Reconectar las cuentas después del cambio. Google puede
    mantener advertencias de aplicación no verificada y un límite de usuarios.

Testing limita estas autorizaciones y refresh tokens a siete días. La excepción
personal sólo cubre a pocas personas conocidas personalmente; si cambia el uso,
revisar la verificación OAuth y los requisitos de datos restringidos. In production
no garantiza tokens permanentes. Ante revocación, el servidor marca `reauth_required`.
Desconectar en el MCP elimina la conexión local; para revocar el consentimiento en
Google, el usuario debe hacerlo desde los permisos de su cuenta Google.

Referencias oficiales:
- https://developers.google.com/workspace/guides/configure-oauth-consent
- https://developers.google.com/workspace/guides/create-credentials
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/identity/protocols/oauth2
- https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification

## Orden de despliegue y túnel

1. Confirmar SSH, hostname/SO/arquitectura, usuario, espacio, memoria, reloj/NTP,
   puerto 8000 libre, Docker/Compose y forma de ejecución de cloudflared.
2. Preparar carpeta, compose, `.env`, claves locales y `data/` protegidos.
3. Para actualizar: respaldar base, `.env` y compose; detener el contenedor antes de migrar.
   Revisar tenants y seguir [la guía de seguridad y migración](../docs/21-seguridad-recursos-y-migracion.md).
   Descargar imagen por digest y ejecutar `alembic upgrade head` con el mismo bind
   de datos y configuración que el contenedor definitivo, antes de arrancarlo.
4. Arrancar y verificar localmente `/health`, rechazo sin JWT, initialize/list/ping.
5. Sólo después modificar el túnel EXISTENTE, con una ruta sin filtro de path:
   hostname `google-mcp.vmmakeup.cl`.
6. Si cloudflared está en el host o red host: origen `http://127.0.0.1:8000`.
7. Si cloudflared está en bridge: usar su red existente, con la pequeña extensión
   `deploy/compose.tunnel.yaml` y `CLOUDFLARED_NETWORK=<nombre observado>`; origen
   `http://google-mcp:8000`. El compose principal también queda activo al usarla.
   En la copia final del servidor se pueden integrar estas entradas en compose.yaml.
8. Confirmar DNS, HTTPS, health y MCP. Conservar las otras rutas, no abrir puertos
   en el router, no crear otro cloudflared. No añadir Cloudflare Access sin comprobar
   compatibilidad con el cliente MCP. Revisar caché/desafíos sobre el hostname.
9. Consentir las cuentas Google y medir recursos. Verificar los servicios existentes.

Rutas reales: `/mcp` Streamable HTTP autenticado; `/health` público;
`/oauth/google/start`, `/oauth/google/status` y `/oauth/google/disconnect` autenticados;
`/oauth/google/callback` público pero con state de 15 minutos y PKCE. El callback
consume state; también lo invalida al cancelar. Los access logs Uvicorn están
 deshabilitados para no registrar códigos en las query strings.

## Pruebas y aceptación

Ejecutar `python -m pytest -q` en un entorno con `.[dev]`; los tests crean su propia
SQLite y claves ficticias y no dependen del `.env` real.

- JWT: inválido, vencido, firma/emisor/audiencia incorrectos o sin sub/iss/aud; sin exp sólo con marcha blanca activa.
- Callback: éxito, error, cancelación, parámetros faltantes, expiración y reutilización.
- HTML: escape de email, móvil/escritorio, sin recursos externos ni excepciones visibles.
- Dos identidades: estado y credenciales aislados; escritura bloqueada sin aprobación.
- HTTP real: health no demuestra readiness de DB/Google; comprobarlas por separado.
- Reinicio y recreación: conservar DB/claves/conexión. Actualización: mismo bind y claves.
- Logs sin secretos, RAM/CPU/OOM, exposición loopback y respuesta desde Internet.
- Git: main local/remoto sincronizados, PR integradas, ramas sin trabajo único eliminadas.

## Copias y rollback

Guardar las copias fuera del directorio reemplazado al actualizar, por ejemplo
`/home/julio/docker/backups/google-mcp/<fecha>/`, con modo 700. Usar la API backup
 de SQLite para una copia consistente, o parar el servicio antes de copiar la DB.
Respaldar `.env` con modo 600 en la misma copia protegida, sin mostrar su contenido.
Registrar digest y revisión Alembic. Probar restauración en una copia aislada.

Para rollback, restaurar digest anterior y, si hay migraciones incompatibles, la
SQLite previa y su clave correspondiente. Nunca regenerar la clave Fernet sobre
una DB existente. `docker compose down` conserva el bind de datos; no borrar data/.

## Cierre con evidencias

Registrar commit/tag/digest, inventario real, límites y consumo, rutas verificadas,
modo OAuth, reinicio/recreación, backup/restore, estado Git y comprobaciones pendientes.
La última imagen QA conocida es una referencia; no se declara funcionamiento en el
Home Lab hasta completar la comprobación local y externa con consentimiento real.
