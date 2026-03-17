# Planificacion del MCP Server Google

Este directorio separa la planificacion acordada para el servidor MCP multiusuario que integrara Google Calendar, Google Tasks y Gmail.

## Archivos

- `docs/01-resumen-y-arquitectura.md`: alcance, enfoque tecnico y arquitectura general.
- `docs/02-autenticacion-y-seguridad.md`: modelo de identidad, OAuth Google, JWT del cliente y controles de seguridad.
- `docs/03-modelo-de-datos-y-tools.md`: entidades principales, tools MCP y comportamiento por servicio.
- `docs/04-backlog-de-implementacion.md`: backlog tecnico por modulos, archivos y orden de implementacion.
- `docs/05-sprint-plan-v1.md`: plan de sprint, prioridades P0/P1/P2, criterios de salida y riesgos.
- `docs/06-guia-desarrollo-local.md`: preparacion del entorno virtual, arranque local y pruebas iniciales.
- `docs/07-despliegue-y-pruebas-e2e.md`: Docker, configuracion Google OAuth y validacion end-to-end.
- `docs/08-validacion-manual-google-real.md`: prueba completa con credenciales Google reales y smoke test MCP.
- `docs/09-checklist-prerrequisitos-prueba-real.md`: checklist operativo para confirmar que ya puedes empezar pruebas reales.
- `docs/10-guia-funcional-primera-prueba.md`: flujo paso a paso para realizar la primera validacion funcional completa.
- `docs/11-guia-tecnica-de-pruebas.md`: herramientas recomendadas y estrategia tecnica por capa de prueba.
- `docs/12-plantilla-env-pruebas-reales.md`: referencia para construir un `.env` realista para pruebas manuales.

## Cambios recientes relevantes

- Se documento el nuevo manejo centralizado de errores Google en `docs/03-modelo-de-datos-y-tools.md`.
- Se agregaron settings y notas operativas para retries Google en `docs/06-guia-desarrollo-local.md`.
- Se amplio la validacion manual real con casos de rate limit, quota y errores clasificados del proveedor en `docs/08-validacion-manual-google-real.md`.

## Alcance de v1

- Servidor MCP remoto con `Python + FastMCP`.
- Multiusuario.
- Autenticacion del cliente con `Bearer JWT`.
- Una cuenta Google conectada por usuario.
- OAuth Google por usuario.
- CRUD para Calendar y Tasks.
- Lectura, drafts, envio y borrado para Gmail.
- `PostgreSQL`, cifrado de tokens y auditoria basica.
