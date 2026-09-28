"""add error_reports table

Revision ID: c4e8a91b2d30
Revises: b7c1e4a02f10
Create Date: 2026-09-03 22:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4e8a91b2d30"
down_revision: str | Sequence[str] | None = "b7c1e4a02f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "error_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("screen", sa.String(length=120), nullable=True),
        sa.Column("stack", sa.Text(), nullable=True),
        sa.Column("app_version", sa.String(length=32), nullable=True),
        sa.Column("platform", sa.String(length=40), nullable=True),
        sa.Column("analysis_id", sa.String(length=36), nullable=True),
        sa.Column("recommendation_id", sa.String(length=36), nullable=True),
        sa.Column("ticket_id", sa.String(length=36), nullable=True),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("error_reports", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_error_reports_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_error_reports_category"), ["category"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_error_reports_analysis_id"), ["analysis_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_error_reports_status"), ["status"], unique=False)
        batch_op.create_index(
            "ix_error_reports_status_created", ["status", "created_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("error_reports", schema=None) as batch_op:
        batch_op.drop_index("ix_error_reports_status_created")
        batch_op.drop_index(batch_op.f("ix_error_reports_status"))
        batch_op.drop_index(batch_op.f("ix_error_reports_analysis_id"))
        batch_op.drop_index(batch_op.f("ix_error_reports_category"))
        batch_op.drop_index(batch_op.f("ix_error_reports_user_id"))
    op.drop_table("error_reports")
