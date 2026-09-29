"""Neutralize the published demo account.

Revision ID: c7a1d4e83b60
Revises: b4d0e2c91a20
Create Date: 2026-09-29

The README password must not authenticate once this migration runs.
Rows belonging to other users are left untouched. Local demo mode re-enables
the same email as a non-admin user from app.seed when YWP_DEMO_MODE=true.
"""

from __future__ import annotations

import secrets

import sqlalchemy as sa
from alembic import op

revision = "c7a1d4e83b60"
down_revision = "b4d0e2c91a20"
branch_labels = None
depends_on = None

_DEMO_EMAIL = "demo@ywp-os.com"


def upgrade() -> None:
    from app.core.security import hash_password

    conn = op.get_bind()
    locked_hash = hash_password(secrets.token_urlsafe(32))
    conn.execute(
        sa.text(
            """
            UPDATE users
            SET role = 'user',
                is_active = :inactive,
                subscription_status = 'inactive',
                subscription_granted_at = NULL,
                password_hash = :password_hash
            WHERE lower(email) = :email
            """
        ),
        {"inactive": False, "password_hash": locked_hash, "email": _DEMO_EMAIL},
    )
    conn.execute(
        sa.text(
            """
            UPDATE refresh_sessions
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE revoked_at IS NULL
              AND user_id IN (
                  SELECT id FROM users WHERE lower(email) = :email
              )
            """
        ),
        {"email": _DEMO_EMAIL},
    )


def downgrade() -> None:
    # The published password is not restored.
    pass
