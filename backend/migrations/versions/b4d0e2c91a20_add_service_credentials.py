"""Add service_credentials for scoped marketing bot tokens.

Revision ID: b4d0e2c91a20
Revises: a3c9a1f82b10
Create Date: 2026-09-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b4d0e2c91a20"
down_revision = "a3c9a1f82b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_credentials",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("rotated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["rotated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_service_credentials_name", "service_credentials", ["name"])
    op.create_index(
        "ix_service_credentials_rotated_by_user_id",
        "service_credentials",
        ["rotated_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_service_credentials_rotated_by_user_id", table_name="service_credentials")
    op.drop_index("ix_service_credentials_name", table_name="service_credentials")
    op.drop_table("service_credentials")
