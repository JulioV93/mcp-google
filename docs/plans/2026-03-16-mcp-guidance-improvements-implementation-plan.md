# MCP guidance improvements implementation plan

## Goal

Improve this Google MCP so agents such as OpenCode can understand how to use Calendar, Tasks, Gmail, and Drive tools with less trial and error, fewer destructive mistakes, and better tool selection.

This plan treats the MCP as more than a raw API surface. The server should actively teach the agent through descriptions, schemas, resources, prompts, error guidance, and safer mutation patterns.

## Current state

- Tools already exist for Calendar, Tasks, Gmail, Drive, and auth.
- Tool descriptions are short and technically correct, but they do not explain decision rules well enough for LLM agents.
- Schemas validate structure, but most fields are not annotated with agent-facing guidance.
- Error payloads are structured, but they do not yet include enough corrective hints.
- Drive already has a strong prepare/confirm model for sensitive mutations.
- There are no MCP resources or prompts that explain how the server should be used.

## Desired outcome

After these improvements, an MCP client should be able to discover not only tools, but also usage guidance:

- which tool to use for each intent
- how to avoid common mistakes
- what safe mutation patterns exist
- what examples are canonical for each domain
- how to recover from common validation and provider errors

## Phased implementation

### Phase 1: Guidance foundation

Scope:
- add MCP resources with usage guides for Calendar, Tasks, Gmail, Drive, safety, and errors
- add MCP prompts that summarize per-domain operating rules
- enrich tool docstrings so tool discovery is more self-explanatory
- extend structured errors with agent-facing guidance fields such as `hint`, `recommended_tool`, and `example_payload`

Files:
- `app/mcp_server.py`
- `app/tools/calendar_tools.py`
- `app/tools/tasks_tools.py`
- `app/tools/gmail_tools.py`
- `app/tools/drive_tools.py`
- `app/errors.py`
- new module for reusable guidance content and MCP registration
- tests for guidance content and error serialization

Success criteria:
- agents can discover explicit guide resources from the MCP
- tool descriptions mention when to use and when not to use a tool
- error payloads can suggest a better tool or example payload

### Phase 2: Schema semantics and examples

Scope:
- add stronger field descriptions to all major schemas
- expose aliases or helper inputs where they reduce LLM ambiguity
- document canonical examples for recurring events, task completion, draft-vs-send, download-vs-export, and prepare-vs-confirm patterns

Files:
- `app/schemas/calendar.py`
- `app/schemas/tasks.py`
- `app/schemas/gmail.py`
- `app/schemas/drive.py`
- docs and MCP example resources

Success criteria:
- schemas communicate intent better in client inspection tools
- common cases can be solved from examples without guesswork

### Phase 3: Safer mutation patterns beyond Drive

Scope:
- evaluate prepare/confirm flow for destructive or high-risk operations outside Drive
- candidate operations: calendar delete, task delete, tasklist delete, optional guarded send-email mode
- classify mutation tools by safety level and confirmation requirement

Files:
- tool modules for destructive operations
- service modules for confirmation workflows
- persistence if pending operations are generalized

Success criteria:
- high-risk operations are harder to trigger accidentally
- the MCP exposes consistent mutation safety semantics across domains

### Phase 4: Response ergonomics for agents

Scope:
- add optional fields such as `resource_identity`, `human_summary`, `next_suggested_actions`, and `safety_level`
- keep current response shapes compatible while improving discoverability

Files:
- service normalization functions across Calendar, Tasks, Gmail, and Drive
- tests for response contracts

Success criteria:
- agents can chain follow-up actions with fewer extra reasoning steps
- clients can understand what to do next from the response alone

### Phase 5: Capability expansion where guidance reveals gaps

Scope:
- Gmail reply helpers
- Gmail archive/label helpers
- Calendar convenience helpers if needed
- richer Drive export guidance and shortcut/share examples

Files:
- domain tool modules, service modules, schemas, tests, and docs

Success criteria:
- the server covers high-frequency intents more directly
- fewer agent workarounds are needed

## Recommended implementation order

1. Phase 1 immediately, because it improves all domains without changing the core data model much.
2. Phase 2 next, because schema semantics reinforce the new guidance resources.
3. Phase 3 after observing agent behavior on risky mutations.
4. Phase 4 once the guidance layer is stable.
5. Phase 5 only after real usage shows which missing capabilities matter most.

## What this change set should implement now

This implementation round should complete the highest-impact items from Phase 1:

- guidance resources for all four domains plus overview, safety, and error handling
- prompt artifacts for all four domains
- improved tool descriptions across Calendar, Tasks, Gmail, and Drive
- richer error payload support with optional hints and example payloads
- tests covering the new guidance and error contract behavior

## Risks and guardrails

- Do not break current tool names or request formats in this phase.
- Keep response shapes backward compatible where possible.
- Keep prompt and resource content concise enough for discovery, but explicit enough to steer tool choice.
- Prefer additive changes over behavioral changes in existing tools.

## Validation plan

- unit tests for guidance content helpers
- unit tests for guided error serialization
- targeted regression tests for Calendar, Tasks, Gmail, and Drive services
- manual inspection of MCP-exposed resources/prompts from a client if available
