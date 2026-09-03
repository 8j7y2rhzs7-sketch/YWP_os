"""add whop subscription tables

Revision ID: b7c1e4a02f10
Revises: ae47f67d9aa5
Create Date: 2026-09-03 16:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7c1e4a02f10"
down_revision: str | Sequence[str] | None = "ae47f67d9aa5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("whop_user_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("whop_membership_id", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("subscription_status", sa.String(length=24), nullable=False, server_default="none")
        )
        batch_op.create_index(batch_op.f("ix_users_whop_user_id"), ["whop_user_id"], unique=False)

    op.create_table(
        "pending_whop_access",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("whop_user_id", sa.String(length=64), nullable=True),
        sa.Column("whop_membership_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("pending_whop_access", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_pending_whop_access_email"), ["email"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_pending_whop_access_whop_user_id"), ["whop_user_id"], unique=False
        )

    op.create_table(
        "whop_webhook_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("webhook_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("whop_webhook_deliveries", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_whop_webhook_deliveries_webhook_id"), ["webhook_id"], unique=True
        )


def downgrade() -> None:
    with op.batch_alter_table("whop_webhook_deliveries", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_whop_webhook_deliveries_webhook_id"))
    op.drop_table("whop_webhook_deliveries")

    with op.batch_alter_table("pending_whop_access", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_pending_whop_access_whop_user_id"))
        batch_op.drop_index(batch_op.f("ix_pending_whop_access_email"))
    op.drop_table("pending_whop_access")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_whop_user_id"))
        batch_op.drop_column("subscription_status")
        batch_op.drop_column("whop_membership_id")
        batch_op.drop_column("whop_user_id")
