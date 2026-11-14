# 文件说明：数据库迁移：0023_evidence_records。
"""Add traceable evidence records.

Revision ID: 0023_evidence_records
Revises: 0022_favorite_kind_folders
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0023_evidence_records"
down_revision: str | None = "0022_favorite_kind_folders"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=True),
        sa.Column("fact_type", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("provider_record_id", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("freshness", sa.String(length=16), nullable=False),
        sa.Column("license_scope", sa.String(length=120), nullable=True),
        sa.Column("raw_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fact_type IN ("
            "'place_fact', 'weather', 'transport', 'lodging_area', "
            "'meal', 'safety', 'attachment'"
            ")",
            name="ck_evidence_records_fact_type",
        ),
        sa.CheckConstraint(
            "freshness IN ('live', 'cached', 'stale', 'mock', 'unknown')",
            name="ck_evidence_records_freshness",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_evidence_records_confidence",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evidence_records_owner_trip_fact",
        "evidence_records",
        ["owner_id", "trip_id", "fact_type"],
    )
    op.create_index(
        "ix_evidence_records_valid_until",
        "evidence_records",
        ["valid_until"],
    )
    op.create_index(
        "uq_evidence_records_owner_provider_record",
        "evidence_records",
        ["owner_id", "fact_type", "provider", "provider_record_id"],
        unique=True,
        postgresql_where=sa.text(
            "trip_id IS NULL AND provider_record_id IS NOT NULL"
        ),
    )
    op.create_index(
        "uq_evidence_records_trip_provider_record",
        "evidence_records",
        [
            "owner_id",
            "trip_id",
            "fact_type",
            "provider",
            "provider_record_id",
        ],
        unique=True,
        postgresql_where=sa.text(
            "trip_id IS NOT NULL AND provider_record_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_evidence_records_trip_provider_record",
        table_name="evidence_records",
    )
    op.drop_index(
        "uq_evidence_records_owner_provider_record",
        table_name="evidence_records",
    )
    op.drop_index(
        "ix_evidence_records_valid_until",
        table_name="evidence_records",
    )
    op.drop_index(
        "ix_evidence_records_owner_trip_fact",
        table_name="evidence_records",
    )
    op.drop_table("evidence_records")
