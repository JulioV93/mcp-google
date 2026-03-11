from __future__ import annotations

from starlette.testclient import TestClient

from app.factory import create_app
from app.logging import redact_value
from app.security.middleware import JWTAuthMiddleware
from app.security.rate_limit import InMemoryRateLimiter, RateLimitExceededError


def test_redaction_hides_sensitive_fields() -> None:
    payload = {
        "subject": "private subject",
        "body_text": "secret body",
        "nested": {"refresh_token": "abc"},
    }

    redacted = redact_value(payload)

    assert redacted["subject"] == "[redacted]"
    assert redacted["body_text"] == "[redacted]"
    assert redacted["nested"]["refresh_token"] == "[redacted]"


def test_in_memory_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter(limit_per_minute=2)
    limiter.check("user-1")
    limiter.check("user-1")

    try:
        limiter.check("user-1")
    except RateLimitExceededError:
        pass
    else:
        raise AssertionError("Expected RateLimitExceededError after exceeding limit")


def test_rate_limit_returns_429_when_limit_is_reached() -> None:
    app = create_app()
    middleware = next(layer.cls for layer in app.user_middleware if layer.cls is JWTAuthMiddleware)
    wrapped = middleware(app)
    wrapped.rate_limiter.limit_per_minute = 1

    with TestClient(wrapped) as client:
        first = client.get("/oauth/google/status", headers={"Authorization": "Bearer local-dev-token"})
        second = client.get("/oauth/google/status", headers={"Authorization": "Bearer local-dev-token"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"] == "rate_limited"
