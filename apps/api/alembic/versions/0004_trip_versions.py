# 文件说明：数据库迁移：0004_trip_versions。
"""Create trip versions table.

Revision ID: 0004_trip_versions
Revises: 0003_itinerary
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_trip_versions"
down_revision: str | None = "0003_itinerary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trip_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_trip_versions_trip_version",
        "trip_versions",
        ["trip_id", "version"],
        unique=True,
    )
    op.create_index(
        "ix_trip_versions_trip_created",
        "trip_versions",
        ["trip_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_trip_versions_trip_created", table_name="trip_versions")
    op.drop_index("uq_trip_versions_trip_version", table_name="trip_versions")
    op.drop_table("trip_versions")
