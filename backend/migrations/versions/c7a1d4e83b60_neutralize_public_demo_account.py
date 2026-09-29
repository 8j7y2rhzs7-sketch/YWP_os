"""Keep the published demo row available for owner adoption.

Revision ID: c7a1d4e83b60
Revises: b4d0e2c91a20
Create Date: 2026-09-29

Do not deactivate demo@ywp-os.com here. That row may be the owner's real
admin account. Startup reads YWP_OWNER_EMAIL and YWP_OWNER_INITIAL_PASSWORD
and either renames it or leaves it unchanged. A later demo@ row is locked
in application code, not in this migration.
"""

from __future__ import annotations

revision = "c7a1d4e83b60"
down_revision = "b4d0e2c91a20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Identity adoption is env-dependent and idempotent, so it runs on startup.
    pass


def downgrade() -> None:
    pass
