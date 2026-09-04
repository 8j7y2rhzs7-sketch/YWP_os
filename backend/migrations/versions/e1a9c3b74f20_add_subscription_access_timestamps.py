"""Track Whop subscription check and grant timestamps.

Revision ID: e1a9c3b74f20
Revises: d8f2a1c90b44
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e1a9c3b74f20"
down_revision = "d8f2a1c90b44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("subscription_checked_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("subscription_granted_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("subscription_granted_at")
        batch_op.drop_column("subscription_checked_at")
