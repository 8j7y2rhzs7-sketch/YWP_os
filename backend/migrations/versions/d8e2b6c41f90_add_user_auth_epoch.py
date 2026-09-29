"""Add users.auth_epoch so rotated logins reject old access tokens.

Revision ID: d8e2b6c41f90
Revises: c7a1d4e83b60
Create Date: 2026-09-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d8e2b6c41f90"
down_revision = "c7a1d4e83b60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_epoch", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "auth_epoch")
