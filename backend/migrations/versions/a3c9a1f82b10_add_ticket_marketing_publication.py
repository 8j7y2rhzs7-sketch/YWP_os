"""Add ticket marketing publication eligibility columns.

Revision ID: a3c9a1f82b10
Revises: f2b8d4e91a30
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a3c9a1f82b10"
down_revision = "f2b8d4e91a30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.add_column(
            sa.Column("publication_eligible", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("publication_eligible_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("publication_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            "ix_tickets_publication_eligible", ["publication_eligible"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_index("ix_tickets_publication_eligible")
        batch_op.drop_column("publication_expires_at")
        batch_op.drop_column("publication_eligible_at")
        batch_op.drop_column("publication_eligible")
