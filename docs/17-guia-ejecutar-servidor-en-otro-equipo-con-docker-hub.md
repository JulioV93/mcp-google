# Ejecutar Google MCP desde Docker Hub

La guía vigente de producción para el Home Lab está en [deploy/README.md](../deploy/README.md).
Usa un único contenedor, SQLite persistente, imagen privada por digest y el Cloudflare
Tunnel existente. El compose es `docker-compose.prod.yml` y la configuración base
es `deploy/.env.mcp-google.example`.

El puerto 8000 se publica sólo en loopback. No utilizar JWT de desarrollo ni añadir
un PostgreSQL para este equipo de 2 GB. El código fuente se mantiene en Git; el Acer
sólo necesita compose.yaml, .env y data/. Construir y publicar la imagen fuera del Acer.

La guía incluye el recorrido funcional GCP, callback HTTPS exacto, aprobación de
escrituras, pruebas, persistencia y restauración. La ejecución se realiza por etapas.
