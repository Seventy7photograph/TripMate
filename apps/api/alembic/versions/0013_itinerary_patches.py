# 文件说明：数据库迁移：0013_itinerary_patches。
"""Add itinerary patches for confirmed partial replans.

Revision ID: 0013_itinerary_patches
Revises: 0012_conversations
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_itinerary_patches"
down_revision: str | None = "0012_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "itinerary_patches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("target_day_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("applied_version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column(
            "changes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["target_day_id"],
            ["trip_days.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_itinerary_patches_trip_created",
        "itinerary_patches",
        ["trip_id", "created_at"],
    )
    op.create_index(
        "ix_itinerary_patches_day",
        "itinerary_patches",
        ["target_day_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_itinerary_patches_day", table_name="itinerary_patches")
    op.drop_index(
        "ix_itinerary_patches_trip_created",
        table_name="itinerary_patches",
    )
    op.drop_table("itinerary_patches")
