from __future__ import annotations

from contextvars import ContextVar
from contextvars import Token as ContextToken

from pydantic import BaseModel, ConfigDict, Field


class RequestContext(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    user_id: str
    subject: str
    issuer: str
    audience: str
    token_type: str = "jwt"
    tenant_id: str | None = None
    email: str | None = None
    approvals: tuple[str, ...] = ()
    claims: dict[str, object] = Field(default_factory=dict)


_request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def set_request_context(context: RequestContext) -> ContextToken[RequestContext | None]:
    return _request_context.set(context)


def reset_request_context(token: ContextToken[RequestContext | None]) -> None:
    _request_context.reset(token)


def get_request_context() -> RequestContext:
    context = _request_context.get()
    if context is None:
        raise RuntimeError("Request context is not available")
    return context


def maybe_get_request_context() -> RequestContext | None:
    return _request_context.get()
