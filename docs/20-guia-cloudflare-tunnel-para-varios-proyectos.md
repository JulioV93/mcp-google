# Reutilizar Cloudflare Tunnel para varios proyectos

Reutilizar el túnel que ya sirve al Home Lab. Añadir únicamente un hostname para
Google MCP: `google-mcp.vmmakeup.cl`, sin filtro de path, después de probar el servicio
local. Mantener las rutas de Uptime Kuma y Hermes. No crear otro túnel ni abrir puertos.

- cloudflared en el host/red host: `http://127.0.0.1:8000`.
- cloudflared en Docker bridge: red existente compartida y `http://google-mcp:8000`.
  Usar `deploy/compose.tunnel.yaml` sólo si la inspección confirma esa necesidad.
- Dentro de un contenedor bridge, localhost pertenece al contenedor.

Verificar DNS, HTTPS, health, MCP con JWT y callback OAuth. La autenticación del
servidor protege las herramientas. Cloudflare Access requiere un análisis específico
 de compatibilidad antes de añadirse.

La guía operativa completa está en [deploy/README.md](../deploy/README.md).
