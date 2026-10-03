"""Persistent authorization profiles; preserve existing Google connections and identities."""

import sqlalchemy as sa
from alembic import op

revision = "20261002_120000"
down_revision = "20261001_120000"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("access_profile", sa.String(20), nullable=False, server_default="read_only")
        )
        batch.create_check_constraint(
            "ck_users_access_profile", "access_profile IN ('read_only', 'read_write', 'disabled')"
        )


def downgrade():
    raise RuntimeError("Access profiles must not be silently removed; use the documented rollback")
