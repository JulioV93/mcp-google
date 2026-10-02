from __future__ import annotations

import base64
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from jwt.exceptions import PyJWKClientConnectionError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from app.config import WRITE_TOOLS, get_settings
from app.db.base import Base
from app.db.models import AuditLog, GoogleConnection, OAuthState, PendingGoogleOperation
from app.db.repositories.users import UserRepository
from app.errors import (
    AppError,
    DriveContentTooLargeError,
    OperationOutcomeUnknownError,
    PermissionProviderError,
    ValidationError,
)
from app.factory import create_app
from app.google.client_base import GoogleApiClientBase
from app.google.drive_client import DriveClient, LimitedDownloadBuffer
from app.logging import audit_arguments
from app.schemas.drive import DriveSearchFilesAdvancedInput
from app.schemas.gmail import (
    GmailConfirmSendEmailInput,
    GmailRecipientMessageInput,
    GmailSendEmailInput,
)
from app.security.jwt_auth import (
    JWTAuthenticationError,
    JWTProviderUnavailableError,
    build_request_context,
    decode_jwt,
    jwks_client,
)
from app.security.middleware import MCPBodyLimitMiddleware
from app.security.rate_limit import InMemoryRateLimiter
from app.services.auth_service import AuthService
from app.services.drive_service import DriveService, _decode_content_payload
from app.services.gmail_service import GmailService
from app.services.maintenance import cleanup
from app.tool_runtime import audited_call


def sessions(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'security.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(params=["sqlite", "postgresql"])
def concurrent_database(tmp_path, request):
    if request.param == "sqlite":
        factory = sessions(tmp_path)
        try:
            yield factory
        finally:
            factory.kw["bind"].dispose()
        return
    import os
    from uuid import uuid4

    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL required for PostgreSQL concurrency")
    admin = create_engine(url)
    schema = "concurrent_test_" + uuid4().hex
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    try:
        Base.metadata.create_all(engine)
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def prepare_email(session, tenant=None):
    return GmailService(session).send_email(
        external_subject="same-subject",
        tenant_id=tenant,
        input_data=GmailSendEmailInput(
            message=GmailRecipientMessageInput(
                to=["test@example.com"], subject="private subject", body_text="private body"
            )
        ),
    )["operation_id"]


def test_tenants_do_not_share_connections_oauth_or_pending_operations(tmp_path):
    factory = sessions(tmp_path)
    with factory() as session:
        users = [
            UserRepository(session).get_or_create("same-subject", tenant)
            for tenant in [None, "a", "b"]
        ]
        session.commit()
        assert len({user.id for user in users}) == 3
        oauth = AuthService(session)
        starts = [
            oauth.begin_google_auth(external_subject="same-subject", tenant_id=tenant)
            for tenant in [None, "a", "b"]
        ]
        assert len({state.state for state in starts}) == 3
        session.add(
            GoogleConnection(
                user_id=users[1].id,
                google_email="a@example.com",
                google_subject="a",
                access_token_encrypted="encrypted",
                status="active",
                granted_scopes=[],
            )
        )
        session.commit()
        assert (
            oauth.get_google_status(external_subject="same-subject", tenant_id="b").connected
            is False
        )
        operation = prepare_email(session, "a")
        service = GmailService(session)
        service.client = Mock()
        with pytest.raises(AppError, match="not found"):
            service.confirm_send_email(
                external_subject="same-subject",
                tenant_id="b",
                input_data=GmailConfirmSendEmailInput(operation_id=operation),
            )
        service.client.send_message.assert_not_called()


@pytest.mark.parametrize("tenant", [None, "", "  ", 1, [], "x" * 256])
def test_invalid_present_tenant_claim_is_rejected(tenant):
    with pytest.raises(JWTAuthenticationError):
        build_request_context({"sub": "user", "tenant_id": tenant})


def test_simultaneous_confirmations_call_google_once(concurrent_database):
    factory = concurrent_database
    with factory() as session:
        operation = prepare_email(session)
    barrier = threading.Barrier(2)
    provider = Mock(return_value={"id": "sent"})

    def confirm():
        with factory() as session:
            service = GmailService(session)
            service.client.send_message = provider
            barrier.wait(timeout=5)
            try:
                return service.confirm_send_email(
                    external_subject="same-subject",
                    input_data=GmailConfirmSendEmailInput(operation_id=operation),
                )["confirmed"]
            except AppError:
                return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: confirm(), range(2)))
    assert sorted(outcomes) == [False, True]
    provider.assert_called_once()
    with factory() as session:
        record = session.scalar(select(PendingGoogleOperation))
        assert record.status == "confirmed"
        assert record.payload_encrypted is None and record.resource_name is None


@pytest.mark.parametrize(
    "failure,status", [(TimeoutError(), "unknown"), (PermissionProviderError("denied"), "failed")]
)
def test_provider_failure_consumes_operation_and_scrubs_payload(tmp_path, failure, status):
    factory = sessions(tmp_path)
    with factory() as session:
        operation = prepare_email(session)
        service = GmailService(session)
        service.client.send_message = Mock(side_effect=failure)
        with pytest.raises(AppError):
            service.confirm_send_email(
                external_subject="same-subject",
                input_data=GmailConfirmSendEmailInput(operation_id=operation),
            )
        record = session.scalar(select(PendingGoogleOperation))
        assert record.status == status and record.payload_encrypted is None
        with pytest.raises(AppError):
            service.confirm_send_email(
                external_subject="same-subject",
                input_data=GmailConfirmSendEmailInput(operation_id=operation),
            )
        service.client.send_message.assert_called_once()


def test_recovery_and_retention_clear_content_and_keep_recent_audit(tmp_path):
    factory = sessions(tmp_path)
    with factory() as session:
        prepare_email(session)
        record = session.scalar(select(PendingGoogleOperation))
        assert "private body" not in record.payload_encrypted
        assert record.payload_normalized["message"]["body_text"] == "private body"
        record.status = "executing"
        user_id = record.user_id
        old = datetime.now(UTC) - timedelta(days=31)
        session.add_all(
            [
                AuditLog(
                    user_id=user_id,
                    tool_name="read",
                    provider="google",
                    resource_type="test",
                    result_status="success",
                    created_at=old,
                ),
                AuditLog(
                    user_id=user_id,
                    tool_name="read",
                    provider="google",
                    resource_type="test",
                    result_status="success",
                ),
            ]
        )
        session.commit()
        cleanup(session, recover=True)
        session.expire_all()
        assert record.status == "unknown" and record.payload_encrypted is None
        assert len(session.scalars(select(AuditLog)).all()) == 1
        with pytest.raises(OperationOutcomeUnknownError):
            GmailService(session).confirm_send_email(
                external_subject="same-subject",
                input_data=GmailConfirmSendEmailInput(operation_id=record.operation_key),
            )
        prepare_email(session, "expired")
        expired = session.scalar(
            select(PendingGoogleOperation).where(PendingGoogleOperation.status == "pending")
        )
        expired.expires_at = old
        session.commit()
        cleanup(session)
        session.expire_all()
        assert expired.status == "expired" and expired.payload_encrypted is None


def test_audit_allowlist_and_failure_preserve_completed_result():
    assert audit_arguments(
        {
            "file_id": "id",
            "content_text": "private",
            "values": [["private"]],
            "to": "private@example.com",
        }
    ) == {"file_id": "id"}
    with patch(
        "app.services.audit_service.AuditService.record_tool_call",
        side_effect=RuntimeError("private"),
    ):
        result = audited_call(
            external_subject="audit-failure",
            tenant_id=None,
            tool_name="write",
            provider="google",
            resource_type="test",
            arguments={},
            operation=lambda _: {"confirmed": True},
        )
    assert result == {"confirmed": True}


@pytest.mark.parametrize(
    "changes",
    [
        {"app_env": "unknown"},
        {"app_env": "production", "jwt_test_mode": True},
        {"jwt_shared_secret": "short"},
        {"jwt_jwks_url": "https://keys.example.com"},
        {"jwt_algorithms": "HS256,RS256"},
    ],
)
def test_invalid_configuration_cannot_start(changes):
    settings = get_settings().model_copy(update=changes)
    with pytest.raises(ValueError):
        settings.validate_startup()


def test_production_policy_requires_all_writes():
    settings = get_settings().model_copy(
        update={
            "app_env": "production",
            "jwt_test_mode": False,
            "require_explicit_approval": True,
            "app_base_url": "https://example.com",
            "google_redirect_uri": "https://example.com/oauth/google/callback",
        }
    )
    settings.validate_startup()
    assert "auth_google_disconnect" in WRITE_TOOLS
    assert "gmail_send_email" not in WRITE_TOOLS
    settings.approval_required_tools = "gmail_confirm_send_email"
    with pytest.raises(ValueError, match="every write"):
        settings.validate_startup()


def test_jwks_cache_and_outage_are_controlled():
    jwks_client.cache_clear()
    assert jwks_client("https://keys.example.com") is jwks_client("https://keys.example.com")
    settings = get_settings().model_copy(
        update={
            "jwt_shared_secret": None,
            "jwt_jwks_url": "https://keys.example.com",
            "jwt_algorithms": "RS256",
        }
    )
    with patch("app.security.jwt_auth.jwks_client") as factory:
        factory.return_value.get_signing_key_from_jwt.side_effect = PyJWKClientConnectionError(
            "private"
        )
        with pytest.raises(JWTProviderUnavailableError):
            decode_jwt("token", settings)
    with (
        TestClient(create_app()) as client,
        patch(
            "app.security.middleware.authenticate_request",
            side_effect=JWTProviderUnavailableError(),
        ),
    ):
        assert (
            client.get(
                "/oauth/google/status", headers={"Authorization": "Bearer token"}
            ).status_code
            == 503
        )


def test_rate_limiter_removes_inactive_tenant_buckets():
    limiter = InMemoryRateLimiter(limit_per_minute=1)
    with patch("app.security.rate_limit.time.monotonic", return_value=0):
        limiter.check(("a", "same"))
        limiter.check(("b", "same"))
    with patch("app.security.rate_limit.time.monotonic", return_value=61):
        limiter.check(("c", "same"))
    assert set(limiter._buckets) == {("c", "same")}


def test_base64_validation_checks_decoded_boundary():
    assert (
        _decode_content_payload(
            {"mime_type": "text/plain", "content_base64": base64.b64encode(b"abcd").decode()}, 4
        )[0]
        == b"abcd"
    )
    with pytest.raises(ValidationError):
        _decode_content_payload({"mime_type": "text/plain", "content_base64": "???="})
    with pytest.raises(DriveContentTooLargeError):
        _decode_content_payload(
            {"mime_type": "text/plain", "content_base64": base64.b64encode(b"abcde").decode()}, 4
        )
    buffer = LimitedDownloadBuffer(4)
    buffer.write(b"abcd")
    with pytest.raises(DriveContentTooLargeError):
        buffer.write(b"e")
    assert buffer.getvalue() == b"abcd"


@pytest.mark.parametrize("export", [False, True])
def test_media_download_stops_before_excess_chunk(tmp_path, export):
    factory = sessions(tmp_path)
    with factory() as session:
        client = DriveClient(
            session, get_settings().model_copy(update={"drive_inline_content_limit_bytes": 4})
        )
        with (
            patch.object(client, "_service", return_value=Mock()),
            patch("app.google.drive_client.MediaIoBaseDownload") as downloader,
        ):

            def chunks(buffer, request, chunksize):
                assert chunksize == 65536
                return SimpleNamespace(
                    next_chunk=Mock(side_effect=lambda: (None, buffer.write(b"abcde")))
                )

            downloader.side_effect = chunks
            with pytest.raises(DriveContentTooLargeError):
                if export:
                    client.export_file(
                        external_subject="user", file_id="id", export_mime_type="text/plain"
                    )
                else:
                    client.download_file(external_subject="user", file_id="id")


def test_all_terms_drive_search_calls_one_identical_query():
    service = DriveService(Mock())
    service.client = Mock()
    service.client.list_files.return_value = {"files": []}
    result = service.search_files_advanced(
        external_subject="user",
        input_data=DriveSearchFilesAdvancedInput(
            terms=["one", "two", "three", "four", "five"], mime_types=["text/plain"]
        ),
    )
    service.client.list_files.assert_called_once()
    assert result["query_used"]["incomplete"] is False


def test_search_budget_reports_incomplete():
    service = DriveService(Mock())
    service.client = Mock()
    service.client.list_files.return_value = {"files": []}
    result = service.search_files_advanced(
        external_subject="user",
        input_data=DriveSearchFilesAdvancedInput(
            terms=["one", "two", "three", "four"],
            mime_types=["a", "b", "c", "d", "e"],
            match_mode="any_term",
        ),
    )
    assert service.client.list_files.call_count == 16
    assert result["query_used"]["incomplete"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("length", [None, "6"])
async def test_http_limit_rejects_before_downstream(length):
    downstream = Mock()
    app = MCPBodyLimitMiddleware(downstream)
    app.limit = 5
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [(b"content-length", length.encode())] if length else [],
    }
    messages = iter(
        [
            {"type": "http.request", "body": b"abc", "more_body": True},
            {"type": "http.request", "body": b"def", "more_body": False},
        ]
    )

    async def receive():
        return next(messages)

    sent = []

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    assert sent[0]["status"] == 413
    downstream.assert_not_called()


def test_oauth_exchange_failure_consumes_state(tmp_path):
    factory = sessions(tmp_path)
    with factory() as session:
        service = AuthService(session)
        start = service.begin_google_auth(external_subject="user")
        with (
            patch("app.services.auth_service.exchange_code", side_effect=TimeoutError()),
            pytest.raises(TimeoutError),
        ):
            service.complete_google_auth(state=start.state, code="code")
        assert session.scalar(select(OAuthState)) is None
        with pytest.raises(ValidationError):
            service.complete_google_auth(state=start.state, code="code")


def test_oauth_worker_does_not_block_health():
    entered, release = threading.Event(), threading.Event()

    def slow_status(**kwargs):
        entered.set()
        assert release.wait(5)
        return SimpleNamespace(
            connected=False,
            google_email=None,
            scopes=[],
            status=None,
            missing_scopes=[],
            status_detail=None,
            recommended_action=None,
        )

    with (
        TestClient(create_app()) as client,
        patch("app.factory.AuthService.get_google_status", side_effect=slow_status),
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        future = pool.submit(
            client.get,
            "/oauth/google/status",
            headers={"Authorization": "Bearer local-dev-token"},
        )
        try:
            assert entered.wait(5)
            assert client.get("/health").status_code == 200
        finally:
            release.set()
        assert future.result(timeout=5).status_code == 200


def test_google_write_request_never_retries_and_clients_are_scoped(tmp_path):
    factory = sessions(tmp_path)
    with factory() as session:
        client = GoogleApiClientBase(session)
        request = Mock(method="POST")
        with patch("app.google.client_base.execute_google_request", return_value={}) as execute:
            client._execute(request)
            assert execute.call_args.kwargs["max_retries"] == 0
        credentials = Mock()
        with (
            patch.object(client.credentials_provider, "get_for_user", return_value=credentials),
            patch("app.google.client_base.AuthorizedHttp"),
            patch("app.google.client_base.build", side_effect=[Mock(), Mock()]) as build,
        ):
            first = client._get_service("drive", "v3", external_subject="same", tenant_id="a")
            assert (
                client._get_service("drive", "v3", external_subject="same", tenant_id="a") is first
            )
            assert (
                client._get_service("drive", "v3", external_subject="same", tenant_id="b")
                is not first
            )
            assert build.call_count == 2


def test_long_retry_after_is_returned_without_early_retry():
    from googleapiclient.errors import HttpError
    from httplib2 import Response

    from app.google.errors import execute_google_request

    request = Mock()
    request.execute.side_effect = HttpError(
        Response({"status": "429", "retry-after": "120"}), b'{"error":{"code":429}}'
    )
    sleep = Mock()
    with pytest.raises(AppError) as caught:
        execute_google_request(
            request, max_retries=3, base_delay_seconds=1, max_delay_seconds=8, sleep_func=sleep
        )
    assert caught.value.metadata["retry_after_seconds"] == 120
    request.execute.assert_called_once()
    sleep.assert_not_called()


def test_provider_error_does_not_echo_sensitive_content():
    from googleapiclient.errors import HttpError
    from httplib2 import Response

    from app.google.errors import map_google_http_error

    error = map_google_http_error(
        HttpError(
            Response({"status": "400"}),
            b'{"error":{"message":"private body secret token","code":400}}',
        )
    )
    assert "private" not in str(error.to_dict())
    assert "secret" not in str(error.to_dict())


def test_http_disconnect_requires_approval_before_provider():
    settings = get_settings().model_copy(update={"require_explicit_approval": True})
    with (
        patch("app.tool_runtime.get_settings", return_value=settings),
        TestClient(create_app()) as client,
        patch("app.factory.AuthService.disconnect_google") as disconnect,
    ):
        result = client.post(
            "/oauth/google/disconnect", headers={"Authorization": "Bearer local-dev-token"}
        )
    assert result.status_code == 403
    disconnect.assert_not_called()


def test_declared_oversized_download_skips_media():
    from app.schemas.drive import DriveDownloadFileInput

    service = DriveService(Mock())
    service.client = Mock()
    service.client.get_file.return_value = {
        "id": "file",
        "mimeType": "application/pdf",
        "size": "10000000",
    }
    with pytest.raises(DriveContentTooLargeError):
        service.download_file(
            external_subject="user", input_data=DriveDownloadFileInput(file_id="file")
        )
    service.client.download_file.assert_not_called()


def test_account_switch_does_not_reuse_old_refresh_token(tmp_path):
    from app.oauth.google_oauth import GoogleOAuthTokens
    from app.security.encryption import encrypt_text

    factory = sessions(tmp_path)
    with factory() as session:
        service = AuthService(session)
        user = service.connections.get_or_create_user(external_subject="switch")
        connection = GoogleConnection(
            user_id=user.id,
            google_email="old@example.com",
            google_subject="old",
            status="active",
            granted_scopes=[],
            access_token_encrypted=encrypt_text("old-access"),
            refresh_token_encrypted=encrypt_text("old-refresh"),
        )
        session.add(connection)
        session.commit()
        service._upsert_google_connection(
            user=user,
            tokens=GoogleOAuthTokens("new-access", None, None, [], None),
            google_email="new@example.com",
            google_subject="new",
        )
        assert connection.refresh_token_encrypted is None


def test_administrator_can_issue_tenant_scoped_approved_jwt(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    import jwt

    env = tmp_path / ".env"
    secret = "test-only-admin-secret-with-at-least-32-bytes"
    env.write_text(
        f"JWT_TEST_MODE=false\nJWT_ALGORITHMS=HS256\nJWT_SHARED_SECRET={secret}\nJWT_ISSUER=urn:test\nJWT_AUDIENCE=google-mcp-server\n"
    )
    output = tmp_path / "approved.token"
    script = Path(__file__).resolve().parents[2] / "scripts/homelab_credentials.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--env",
            str(env),
            "issue-token",
            "--subject",
            "user",
            "--tenant-id",
            "tenant-a",
            "--approve-tool",
            "gmail_confirm_send_email",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    token = output.read_text().strip()
    payload = jwt.decode(
        token, secret, algorithms=["HS256"], issuer="urn:test", audience="google-mcp-server"
    )
    assert payload["tenant_id"] == "tenant-a"
    assert payload["approved_tools"] == ["gmail_confirm_send_email"]
    assert output.stat().st_mode & 0o777 == 0o600
    assert token not in result.stdout


def test_uncertain_direct_write_is_not_reported_as_retryable(tmp_path):
    from app.errors import TemporaryProviderError

    factory = sessions(tmp_path)
    with factory() as session:
        client = GoogleApiClientBase(session)
        with patch(
            "app.google.client_base.execute_google_request",
            side_effect=TemporaryProviderError("failed"),
        ):
            with pytest.raises(OperationOutcomeUnknownError) as caught:
                client._execute(Mock(method="POST"))
            assert caught.value.retryable is False


def test_concurrent_user_creation_reuses_identity(concurrent_database):
    barrier = threading.Barrier(2)

    def create():
        with concurrent_database() as session:
            barrier.wait(timeout=5)
            user = UserRepository(session).get_or_create("race", "tenant")
            session.commit()
            return user.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        identities = list(pool.map(lambda _: create(), range(2)))
    assert len(set(identities)) == 1


def test_mcp_http_transport_preserves_authenticated_context():
    headers = {
        "Authorization": "Bearer local-dev-token",
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(create_app()) as client:
        response = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "security-check", "version": "1"},
                },
            },
        )
        assert response.status_code == 200
        headers["Mcp-Session-Id"] = response.headers["mcp-session-id"]
        response = client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        assert response.status_code == 202
        response = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "ping", "arguments": {}},
            },
        )
        assert response.status_code == 200
        assert "local-dev-user" in response.text
        assert "anonymous" not in response.text


def test_stale_expiration_cannot_overwrite_claimed_operation(concurrent_database):
    from app.db.repositories.pending_google_operations import PendingGoogleOperationRepository

    with concurrent_database() as creator:
        key = prepare_email(creator)
    with concurrent_database() as stale, concurrent_database() as claimant:
        stale_repo = PendingGoogleOperationRepository(stale)
        record = stale_repo.get_by_operation_key(key)
        claim_repo = PendingGoogleOperationRepository(claimant)
        assert claim_repo.claim(claim_repo.get_by_operation_key(key))
        stale_repo.mark_expired(record)
        stale.commit()
        stale.refresh(record)
        assert record.status == "executing"
        assert record.payload_encrypted is not None


def test_logging_removes_dependency_tracebacks_and_oauth_query_secrets():
    import logging
    import sys

    from app.logging import RedactionFilter

    try:
        raise RuntimeError("provider-secret-must-not-leak")
    except RuntimeError:
        record = logging.LogRecord(
            "dependency",
            logging.ERROR,
            __file__,
            1,
            "Request %s",
            ("/oauth/google/callback?code=private-code&state=private-state",),
            sys.exc_info(),
        )
    assert RedactionFilter().filter(record)
    output = logging.Formatter().format(record)
    assert "provider-secret-must-not-leak" not in output
    assert "private-code" not in output and "private-state" not in output
    assert "[redacted]" in output
