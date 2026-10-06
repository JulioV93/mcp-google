from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, get_args

from fastmcp import FastMCP
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from pydantic_core import ErrorType

from app.config import get_settings
from app.context.request_context import maybe_get_request_context
from app.errors import AppError, UnauthorizedError, ValidationError
from app.security.authorization import authorize_tool
from app.security.tool_policy import tool_annotations
from app.tool_runtime import audited_call


def register_ping_tool(mcp: FastMCP, *, server_name: str, server_version: str) -> None:
    @mcp.tool(annotations=tool_annotations("ping"))
    def ping() -> dict[str, str]:
        """Return the current server status."""
        context = maybe_get_request_context()
        if context is not None:
            return run_tool(
                tool_name="ping",
                provider="google",
                resource_type="server",
                arguments={},
                operation=lambda session, context: {
                    "status": "ok",
                    "server": server_name,
                    "version": server_version,
                    "subject": context.subject,
                    "token_type": context.token_type,
                },
            )
        return {
            "status": "ok",
            "server": server_name,
            "version": server_version,
            "subject": context.subject if context else "anonymous",
            "token_type": context.token_type if context else "none",
        }


def require_context():
    context = maybe_get_request_context()
    if context is None:
        raise UnauthorizedError("Authenticated request context is required")
    return context


def run_tool(
    *,
    tool_name: str,
    provider: str,
    resource_type: str,
    arguments: dict[str, object],
    operation: Callable[[Any, Any], dict[str, object]],
) -> dict[str, object]:
    context = require_context()
    try:

        def authorized_operation(session):
            authorize_tool(
                session,
                settings=get_settings(),
                subject=context.subject,
                tenant_id=context.tenant_id,
                tool_name=tool_name,
                approved_tools=context.approvals,
            )
            return operation(session, context)

        return audited_call(
            external_subject=context.subject,
            tenant_id=context.tenant_id,
            tool_name=tool_name,
            provider=provider,
            resource_type=resource_type,
            arguments=arguments,
            operation=authorized_operation,
        )
    except AppError as exc:
        raise exc.to_tool_error() from exc


ModelT = TypeVar("ModelT", bound=BaseModel)


def validate_tool_payload(model: type[ModelT], arguments: dict[str, object]) -> ModelT:
    """Expose fixed schema paths and error codes, never input values or exception text."""
    try:
        return model.model_validate(arguments)
    except PydanticValidationError as exc:
        schema = model.model_json_schema()
        known_fields = set(schema.get("properties", {}))
        for definition in schema.get("$defs", {}).values():
            known_fields.update(definition.get("properties", {}))
        builtin_types = set(get_args(ErrorType))
        errors = [
            {
                "field": ".".join(
                    str(part)
                    if isinstance(part, int) or part in known_fields
                    else "<unknown_field>"
                    for part in error["loc"]
                ),
                "type": error["type"] if error["type"] in builtin_types else "value_error",
            }
            for error in exc.errors(include_input=False, include_context=False, include_url=False)
        ]
        raise ValidationError(
            "Invalid tool fields",
            hint="Correct the indicated fields before retrying; do not repeat the same payload.",
            expected_fields=sorted({error["field"] for error in errors}),
            metadata={"validation_errors": errors},
        ).to_tool_error() from None
