"""Add ticket-level wager settlement columns.

Revision ID: d8f2a1c90b44
Revises: c4e8a91b2d30
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d8f2a1c90b44"
down_revision = "c4e8a91b2d30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.add_column(sa.Column("settled_outcome", sa.String(length=24), nullable=True))
        batch_op.add_column(
            sa.Column("settled_payout", sa.Numeric(precision=14, scale=2), nullable=True)
        )
        batch_op.add_column(
            sa.Column("settled_profit_loss", sa.Numeric(precision=14, scale=2), nullable=True)
        )
        batch_op.add_column(sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_column("settled_at")
        batch_op.drop_column("settled_profit_loss")
        batch_op.drop_column("settled_payout")
        batch_op.drop_column("settled_outcome")
