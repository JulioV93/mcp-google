# Error Handling Refactor Design

## Objective

Improve error propagation across HTTP, MCP tools, services, and Google provider clients so the system preserves structured error codes, uses better status codes, and distinguishes provider failures from internal server bugs.

## Current Problems

- Google HTTP errors are mapped once but then flattened to strings in client and service layers.
- MCP tool execution converts typed application errors into `RuntimeError`, losing machine-readable structure.
- Unexpected internal exceptions are reclassified as `provider_error`.
- OAuth callback returns `400 provider_error` for both expected provider issues and unexpected internal faults.

## Design Goals

- Preserve typed errors across layers.
- Keep stable `error` codes for agents and HTTP clients.
- Distinguish client, provider, and internal failures.
- Add retryability and category metadata without breaking the current response shape.
- Log unexpected errors with stack traces only once at the boundary.

## Exception Hierarchy

- `AppError`
  - common fields: `code`, `detail`, `status_code`, `retryable`, `category`, `metadata`
- `ValidationError`
- `UnauthorizedError`
- `ApprovalRequiredError`
- `OriginNotAllowedError`
- `RateLimitedError`
- `ProviderError`
  - `AuthenticationProviderError`
  - `PermissionProviderError`
  - `NotFoundProviderError`
  - `TemporaryProviderError`
- `InternalError`
- `ConfigurationError`

## Propagation Rules

### Provider Clients

- Map Google `HttpError` directly to typed `ProviderError` subclasses.
- Do not wrap provider errors as plain strings.

### Services

- Re-raise `AppError` unchanged.
- Only raise service-specific exceptions if they add real business context.
- For this refactor, minimize service-specific wrappers and keep `AppError` flowing.

### Tool Runtime

- Audit and re-raise `AppError` unchanged.
- Convert unexpected exceptions to `InternalError`.
- Log unexpected exceptions with stack trace before conversion.

### Tool Boundary

- Do not downgrade `AppError` to `RuntimeError`.
- Let typed errors propagate to FastMCP.

### HTTP Boundary

- Convert `AppError` to JSON using `status_code`, `code`, `detail`, `retryable`, `category`, and optional `metadata`.
- Convert unexpected exceptions to `500 internal_error` and log stack traces.

## Response Shape

Keep the current `error` and `detail` fields, and enrich responses with:

```json
{
  "error": "insufficient_scope",
  "detail": "Request had insufficient authentication scopes.",
  "retryable": false,
  "category": "provider"
}
```

Optional `metadata` should be included only when useful.

## Migration Plan

1. Refactor `app/errors.py` to support richer typed errors.
2. Update `app/google/errors.py` to map provider failures more precisely.
3. Stop string-flattening in Google clients and services.
4. Update `app/tool_runtime.py` and `app/tools/common.py` to preserve `AppError`.
5. Add HTTP helpers in `app/factory.py` to serialize typed errors consistently.
6. Add regression tests for provider, runtime, and HTTP boundaries.

## Success Criteria

- `insufficient_scope` remains structured from Google client through MCP/HTTP output.
- Unexpected bugs no longer appear as `provider_error`.
- OAuth callback returns `500 internal_error` for internal faults.
- Auditing records stable error codes.
- Existing tests continue to pass, with new coverage for typed error propagation.
