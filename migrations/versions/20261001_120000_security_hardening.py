"""Tenant isolation, encrypted pending content and historical audit sanitation.

Revision ID: 20261001_120000
Revises: 20260314_120000
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet

from app.config import get_settings
from app.logging import audit_arguments

revision = "20261001_120000"
down_revision = "20260314_120000"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    key = Fernet(get_settings().token_encryption_key.encode("ascii"))
    bind.execute(sa.text("UPDATE users SET tenant_id = '' WHERE tenant_id IS NULL"))
    constraint = next(
        c
        for c in sa.inspect(bind).get_unique_constraints("users")
        if c["column_names"] == ["external_subject"]
    )
    with op.batch_alter_table(
        "users", naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}
    ) as batch:
        batch.drop_constraint(constraint["name"] or "uq_users_external_subject", type_="unique")
        batch.alter_column(
            "tenant_id", existing_type=sa.String(255), nullable=False, server_default=""
        )
        batch.create_unique_constraint("uq_users_tenant_subject", ["tenant_id", "external_subject"])
    op.add_column(
        "pending_google_operations", sa.Column("payload_encrypted", sa.Text(), nullable=True)
    )
    metadata = sa.MetaData()
    pending = sa.Table("pending_google_operations", metadata, autoload_with=bind)
    audit = sa.Table("audit_logs", metadata, autoload_with=bind)
    now = datetime.now(UTC)
    last_id = 0
    while True:
        rows = (
            bind.execute(
                sa.select(pending).where(pending.c.id > last_id).order_by(pending.c.id).limit(500)
            )
            .mappings()
            .all()
        )
        if not rows:
            break
        for row in rows:
            expiry = row["expires_at"]
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)
            valid = row["status"] == "pending" and expiry > now
            encrypted = (
                key.encrypt(
                    json.dumps(
                        row["payload_normalized"], sort_keys=True, separators=(",", ":")
                    ).encode()
                ).decode()
                if valid
                else None
            )
            bind.execute(
                pending.update()
                .where(pending.c.id == row["id"])
                .values(
                    payload_encrypted=encrypted,
                    payload_normalized={},
                    payload_hash=row["payload_hash"] if valid else "",
                    resource_name=row["resource_name"] if valid else None,
                    status="expired" if row["status"] == "pending" and not valid else row["status"],
                )
            )
        last_id = rows[-1]["id"]
    last_id = 0
    while True:
        rows = (
            bind.execute(
                sa.select(audit.c.id, audit.c.arguments_redacted)
                .where(audit.c.id > last_id)
                .order_by(audit.c.id)
                .limit(500)
            )
            .mappings()
            .all()
        )
        if not rows:
            break
        for row in rows:
            bind.execute(
                audit.update()
                .where(audit.c.id == row["id"])
                .values(arguments_redacted=audit_arguments(row["arguments_redacted"]))
            )
        last_id = rows[-1]["id"]
    bind.execute(audit.delete().where(audit.c.created_at < now - timedelta(days=30)))
    with op.batch_alter_table("pending_google_operations") as batch:
        batch.drop_column("payload_normalized")
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade():
    raise RuntimeError(
        "Restore a protected backup and the previous image; plaintext downgrade is unsupported"
    )
