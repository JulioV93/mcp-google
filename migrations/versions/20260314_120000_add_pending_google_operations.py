"""add pending google operations

Revision ID: 20260314_120000
Revises: 20260310_180900
Create Date: 2026-03-14 12:00:00

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260314_120000"
down_revision = "20260310_180900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_google_operations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("operation_key", sa.String(length=64), nullable=False),
        sa.Column("operation_type", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("resource_name", sa.String(length=255), nullable=True),
        sa.Column("payload_normalized", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_key"),
    )
    op.create_index(op.f("ix_pending_google_operations_user_id"), "pending_google_operations", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_pending_google_operations_operation_key"),
        "pending_google_operations",
        ["operation_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pending_google_operations_operation_type"),
        "pending_google_operations",
        ["operation_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pending_google_operations_status"),
        "pending_google_operations",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pending_google_operations_expires_at"),
        "pending_google_operations",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pending_google_operations_expires_at"), table_name="pending_google_operations")
    op.drop_index(op.f("ix_pending_google_operations_status"), table_name="pending_google_operations")
    op.drop_index(op.f("ix_pending_google_operations_operation_type"), table_name="pending_google_operations")
    op.drop_index(op.f("ix_pending_google_operations_operation_key"), table_name="pending_google_operations")
    op.drop_index(op.f("ix_pending_google_operations_user_id"), table_name="pending_google_operations")
    op.drop_table("pending_google_operations")
