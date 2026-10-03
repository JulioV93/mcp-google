from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.security.encryption import decrypt_text


@pytest.mark.parametrize("backend", ["sqlite", "postgresql"])
def test_existing_data_migrates_without_plaintext_or_lost_identity(tmp_path, monkeypatch, backend):
    schema = None
    admin = None
    if backend == "postgresql":
        url = os.environ.get("TEST_POSTGRES_URL")
        if not url:
            pytest.skip("TEST_POSTGRES_URL is required for PostgreSQL migration validation")
        admin = create_engine(url)
        schema = "security_test_" + uuid4().hex
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = (
            make_url(url)
            .update_query_dict({"options": f"-csearch_path={schema}"})
            .render_as_string(hide_password=False)
        )
    else:
        url = f"sqlite:///{tmp_path / 'migration.db'}"
    settings = get_settings().model_copy(update={"database_url": url})
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[2] / "migrations")
    )
    engine = create_engine(url)
    try:
        command.upgrade(config, "20260314_120000")
        now = datetime.now(UTC)
        payload = {"message": {"body_text": "private legacy content"}}
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (external_subject,tenant_id) VALUES ('same',NULL),('tenant-user','tenant-a')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO google_connections (id,user_id,google_email,google_subject,status,granted_scopes,access_token_encrypted,refresh_token_encrypted) VALUES (1,1,'test@example.com','google','active','[]','preserved-access','preserved-refresh')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO pending_google_operations (id,user_id,provider,operation_key,operation_type,resource_type,payload_normalized,payload_hash,status,expires_at,resource_name) VALUES (1,1,'google','operation','gmail_send','gmail_message',:payload,'hash','pending',:expiry,'private name')"
                ),
                {
                    "payload": json.dumps(payload),
                    "expiry": (now + timedelta(minutes=5)).isoformat(" ")
                    if backend == "sqlite"
                    else now + timedelta(minutes=5),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO audit_logs (id,user_id,tool_name,provider,resource_type,arguments_redacted,result_status) VALUES (1,1,'write','google','file',:args,'success')"
                ),
                {"args": json.dumps({"content_text": "private", "file_id": "file-1"})},
            )
        command.upgrade(config, "head")
        with engine.connect() as conn:
            users = conn.execute(text("SELECT id,tenant_id FROM users ORDER BY id")).all()
            assert users == [(1, ""), (2, "tenant-a")]
            assert conn.execute(text("SELECT access_profile FROM users ORDER BY id")).all() == [
                ("read_only",),
                ("read_only",),
            ]
            assert conn.execute(
                text(
                    "SELECT access_token_encrypted,refresh_token_encrypted FROM google_connections"
                )
            ).one() == ("preserved-access", "preserved-refresh")
            encrypted = conn.execute(
                text("SELECT payload_encrypted FROM pending_google_operations")
            ).scalar_one()
            assert "private legacy content" not in encrypted
            assert json.loads(decrypt_text(encrypted, settings)) == payload
            args = conn.execute(text("SELECT arguments_redacted FROM audit_logs")).scalar_one()
            assert (json.loads(args) if isinstance(args, str) else args) == {"file_id": "file-1"}
            assert "payload_normalized" not in {
                c["name"] for c in inspect(conn).get_columns("pending_google_operations")
            }
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (external_subject,tenant_id) VALUES ('same','tenant-b')")
            )
        command.upgrade(config, "head")
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
