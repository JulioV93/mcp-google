from __future__ import annotations

from starlette.testclient import TestClient

from app.factory import create_app
from app.security.jwt_auth import build_request_context


def test_mcp_rejects_disallowed_origin() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get(
            "/mcp",
            headers={
                "Authorization": "Bearer local-dev-token",
                "Origin": "https://malicious.example",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"] == "origin_not_allowed"


def test_request_context_captures_approved_tools_claim() -> None:
    context = build_request_context(
        {
            "sub": "user-1",
            "iss": "issuer",
            "aud": "audience",
            "approved_tools": ["gmail_send_email"],
        }
    )

    assert context.approvals == ("gmail_send_email",)
