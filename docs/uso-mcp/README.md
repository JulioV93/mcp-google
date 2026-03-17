# Plantillas OpenCode + MCP Google Calendar

Este directorio contiene plantillas listas para copiar y adaptar en OpenCode.

Objetivo:
- configurar el servidor MCP `google-mcp`
- ensenar a OpenCode a crear eventos recurrentes con `calendar_create_event`
- evitar que el agente cree multiples eventos cuando basta con un solo evento con `event.recurrence`

Archivos incluidos:
- `docs/uso-mcp/opencode.proyecto.jsonc`: ejemplo de configuracion por proyecto
- `docs/uso-mcp/opencode.global.jsonc`: ejemplo de configuracion global
- `docs/uso-mcp/opencode.agente.jsonc`: ejemplo para registrar un agente especializado
- `docs/uso-mcp/google-calendar-rules.md`: reglas y escenarios de recurrencia para instrucciones compartidas
- `docs/uso-mcp/calendar-agent.txt`: prompt de agente especializado en Google Calendar

Uso sugerido:
1. Si quieres que aplique solo a este repo, usa `docs/uso-mcp/opencode.proyecto.jsonc` como base para tu `opencode.json`.
2. Si quieres la regla en todos tus proyectos, usa `docs/uso-mcp/opencode.global.jsonc` como base para `~/.config/opencode/opencode.json`.
3. Si quieres maxima precision, agrega tambien el agente definido en `docs/uso-mcp/opencode.agente.jsonc` y el prompt `docs/uso-mcp/calendar-agent.txt`.
4. Copia el contenido de `docs/uso-mcp/google-calendar-rules.md` al archivo de instrucciones que referencies desde OpenCode.

Regla principal:
- si el usuario pide un evento recurrente, OpenCode debe crear un solo `calendar_create_event` con `event.recurrence`
- no debe simular la recurrencia creando multiples eventos separados

Documentacion de referencia en este repo:
- `docs/13-guia-conectar-mcp-a-opencode.md`
- `docs/16-system-prompt-opencode-errores-mcp.md`
- `docs/03-modelo-de-datos-y-tools.md`
- `docs/06-guia-desarrollo-local.md`
