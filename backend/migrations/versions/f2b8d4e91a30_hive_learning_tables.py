"""Add YWP Hive learning tables.

Revision ID: f2b8d4e91a30
Revises: e1a9c3b74f20
Create Date: 2026-09-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2b8d4e91a30"
down_revision: str | Sequence[str] | None = "e1a9c3b74f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hive_learning_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("contributor_key", sa.String(length=64), nullable=False),
        sa.Column("source_recommendation_id", sa.String(length=128), nullable=False),
        sa.Column("sport", sa.String(length=32), nullable=False),
        sa.Column("league", sa.String(length=64), nullable=True),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("event_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("market", sa.String(length=64), nullable=False),
        sa.Column("market_scope", sa.String(length=96), nullable=False),
        sa.Column("selection", sa.String(length=256), nullable=False),
        sa.Column("line", sa.Float(), nullable=True),
        sa.Column("odds_american", sa.Integer(), nullable=True),
        sa.Column("model_probability", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("protocol_version", sa.String(length=64), nullable=True),
        sa.Column("evidence_version", sa.String(length=128), nullable=True),
        sa.Column("data_quality", sa.Float(), nullable=True),
        sa.Column("feature_flags", sa.JSON(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=True),
        sa.Column("outcome", sa.String(length=8), nullable=True),
        sa.Column("outcome_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("result_source", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_to_hive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "training_eligible", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("training_ineligibility_reason", sa.String(length=96), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "model_probability IS NULL OR (model_probability >= 0 AND model_probability <= 1)",
            name="ck_hive_probability",
        ),
        sa.CheckConstraint(
            "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 100)",
            name="ck_hive_quality",
        ),
        sa.CheckConstraint(
            "data_quality IS NULL OR (data_quality >= 0 AND data_quality <= 1)",
            name="ck_hive_data_quality",
        ),
        sa.CheckConstraint(
            "action IS NULL OR action IN ('accepted','rejected','ignored')",
            name="ck_hive_action",
        ),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('WIN','LOSS','PUSH','VOID')",
            name="ck_hive_outcome",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_hive_learning_events_idempotency_key",
        "hive_learning_events",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_hive_learning_events_contributor_key",
        "hive_learning_events",
        ["contributor_key"],
        unique=False,
    )
    op.create_index(
        "ix_hive_learning_events_source_recommendation_id",
        "hive_learning_events",
        ["source_recommendation_id"],
        unique=False,
    )
    op.create_index(
        "ix_hive_learning_events_sport", "hive_learning_events", ["sport"], unique=False
    )
    op.create_index(
        "ix_hive_learning_events_league", "hive_learning_events", ["league"], unique=False
    )
    op.create_index(
        "ix_hive_learning_events_event_id", "hive_learning_events", ["event_id"], unique=False
    )
    op.create_index(
        "ix_hive_learning_events_market", "hive_learning_events", ["market"], unique=False
    )
    op.create_index(
        "ix_hive_learning_events_market_scope",
        "hive_learning_events",
        ["market_scope"],
        unique=False,
    )
    op.create_index(
        "ix_hive_learning_events_model_version",
        "hive_learning_events",
        ["model_version"],
        unique=False,
    )
    op.create_index(
        "ix_hive_learning_events_outcome", "hive_learning_events", ["outcome"], unique=False
    )
    op.create_index(
        "ix_hive_learning_events_training_eligible",
        "hive_learning_events",
        ["training_eligible"],
        unique=False,
    )
    op.create_index(
        "ix_hive_event_bucket",
        "hive_learning_events",
        ["sport", "league", "market", "market_scope", "model_version", "training_eligible"],
        unique=False,
    )

    op.create_table(
        "hive_aggregates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("bucket_key", sa.String(length=64), nullable=False),
        sa.Column("sport", sa.String(length=32), nullable=False),
        sa.Column("league", sa.String(length=64), nullable=True),
        sa.Column("market", sa.String(length=64), nullable=False),
        sa.Column("market_scope", sa.String(length=96), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("eligible_samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pushes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("voids", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "sum_predicted_probability", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column(
            "predicted_probability_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("raw_rate", sa.Float(), nullable=True),
        sa.Column("posterior_rate", sa.Float(), nullable=True),
        sa.Column("mean_predicted_probability", sa.Float(), nullable=True),
        sa.Column("calibration_delta", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket_key"),
    )
    op.create_index(
        "ix_hive_aggregates_bucket_key", "hive_aggregates", ["bucket_key"], unique=True
    )
    op.create_index("ix_hive_aggregates_sport", "hive_aggregates", ["sport"], unique=False)
    op.create_index("ix_hive_aggregates_league", "hive_aggregates", ["league"], unique=False)
    op.create_index("ix_hive_aggregates_market", "hive_aggregates", ["market"], unique=False)
    op.create_index(
        "ix_hive_aggregates_market_scope", "hive_aggregates", ["market_scope"], unique=False
    )
    op.create_index(
        "ix_hive_aggregates_model_version", "hive_aggregates", ["model_version"], unique=False
    )
    op.create_index(
        "ix_hive_aggregate_lookup",
        "hive_aggregates",
        ["sport", "league", "market", "market_scope", "model_version"],
        unique=False,
    )

    op.create_table(
        "hive_model_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("release_version", sa.String(length=64), nullable=False),
        sa.Column(
            "snapshot_type",
            sa.String(length=32),
            nullable=False,
            server_default="aggregate_release",
        ),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "release_version", "snapshot_type", name="uq_hive_snapshot_release_type"
        ),
    )
    op.create_index(
        "ix_hive_model_snapshots_release_version",
        "hive_model_snapshots",
        ["release_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_hive_model_snapshots_release_version", table_name="hive_model_snapshots")
    op.drop_table("hive_model_snapshots")
    op.drop_index("ix_hive_aggregate_lookup", table_name="hive_aggregates")
    op.drop_index("ix_hive_aggregates_model_version", table_name="hive_aggregates")
    op.drop_index("ix_hive_aggregates_market_scope", table_name="hive_aggregates")
    op.drop_index("ix_hive_aggregates_market", table_name="hive_aggregates")
    op.drop_index("ix_hive_aggregates_league", table_name="hive_aggregates")
    op.drop_index("ix_hive_aggregates_sport", table_name="hive_aggregates")
    op.drop_index("ix_hive_aggregates_bucket_key", table_name="hive_aggregates")
    op.drop_table("hive_aggregates")
    op.drop_index("ix_hive_event_bucket", table_name="hive_learning_events")
    op.drop_index("ix_hive_learning_events_training_eligible", table_name="hive_learning_events")
    op.drop_index("ix_hive_learning_events_outcome", table_name="hive_learning_events")
    op.drop_index("ix_hive_learning_events_model_version", table_name="hive_learning_events")
    op.drop_index("ix_hive_learning_events_market_scope", table_name="hive_learning_events")
    op.drop_index("ix_hive_learning_events_market", table_name="hive_learning_events")
    op.drop_index("ix_hive_learning_events_event_id", table_name="hive_learning_events")
    op.drop_index("ix_hive_learning_events_league", table_name="hive_learning_events")
    op.drop_index("ix_hive_learning_events_sport", table_name="hive_learning_events")
    op.drop_index(
        "ix_hive_learning_events_source_recommendation_id", table_name="hive_learning_events"
    )
    op.drop_index("ix_hive_learning_events_contributor_key", table_name="hive_learning_events")
    op.drop_index("ix_hive_learning_events_idempotency_key", table_name="hive_learning_events")
    op.drop_table("hive_learning_events")
