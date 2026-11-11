"""Add day-prep schedule, plays, and learned lead tables.

Revision ID: c9e4b1a72d55
Revises: 82e84f59efc9
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9e4b1a72d55"
down_revision: str | Sequence[str] | None = "82e84f59efc9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "day_prep_days",
        sa.Column("slate_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notice", sa.Text(), nullable=False),
        sa.Column("schedule_pulled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priced_pulled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pricing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pull2_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("earliest_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lead_minutes", sa.Integer(), nullable=True),
        sa.Column("binding_sport", sa.String(length=24), nullable=True),
        sa.Column("completeness", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("slate_date"),
    )
    op.create_index("ix_day_prep_days_status", "day_prep_days", ["status"], unique=False)
    op.create_table(
        "day_prep_games",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slate_date", sa.Date(), nullable=False),
        sa.Column("sport", sa.String(length=24), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("event_name", sa.String(length=180), nullable=False),
        sa.Column("home_team", sa.String(length=80), nullable=False),
        sa.Column("away_team", sa.String(length=80), nullable=False),
        sa.Column("commence_time", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slate_date", "sport", "event_id", name="uq_day_prep_game"),
    )
    op.create_index("ix_day_prep_games_slate", "day_prep_games", ["slate_date", "commence_time"])
    op.create_index("ix_day_prep_games_slate_date", "day_prep_games", ["slate_date"])
    op.create_index("ix_day_prep_games_sport", "day_prep_games", ["sport"])
    op.create_table(
        "day_prep_plays",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slate_date", sa.Date(), nullable=False),
        sa.Column("sport", sa.String(length=24), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("selection", sa.String(length=180), nullable=False),
        sa.Column("market_type", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_day_prep_plays_slate", "day_prep_plays", ["slate_date", "sport", "rank"])
    op.create_index("ix_day_prep_plays_slate_date", "day_prep_plays", ["slate_date"])
    op.create_index("ix_day_prep_plays_sport", "day_prep_plays", ["sport"])
    op.create_table(
        "day_prep_leads",
        sa.Column("sport", sa.String(length=24), nullable=False),
        sa.Column("lead_minutes", sa.Integer(), nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False),
        sa.Column("last_completeness", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("last_minutes_before", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("sport"),
    )
    op.create_table(
        "day_prep_claims",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("slate_date", sa.Date(), nullable=False),
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "slate_date", name="uq_day_prep_claim"),
    )
    op.create_index("ix_day_prep_claims_analysis_id", "day_prep_claims", ["analysis_id"])
    op.create_index("ix_day_prep_claims_slate_date", "day_prep_claims", ["slate_date"])
    op.create_index("ix_day_prep_claims_user_id", "day_prep_claims", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_day_prep_claims_user_id", table_name="day_prep_claims")
    op.drop_index("ix_day_prep_claims_slate_date", table_name="day_prep_claims")
    op.drop_index("ix_day_prep_claims_analysis_id", table_name="day_prep_claims")
    op.drop_table("day_prep_claims")
    op.drop_table("day_prep_leads")
    op.drop_index("ix_day_prep_plays_sport", table_name="day_prep_plays")
    op.drop_index("ix_day_prep_plays_slate_date", table_name="day_prep_plays")
    op.drop_index("ix_day_prep_plays_slate", table_name="day_prep_plays")
    op.drop_table("day_prep_plays")
    op.drop_index("ix_day_prep_games_sport", table_name="day_prep_games")
    op.drop_index("ix_day_prep_games_slate_date", table_name="day_prep_games")
    op.drop_index("ix_day_prep_games_slate", table_name="day_prep_games")
    op.drop_table("day_prep_games")
    op.drop_index("ix_day_prep_days_status", table_name="day_prep_days")
    op.drop_table("day_prep_days")
