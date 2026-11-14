# 文件说明：数据库迁移：0014_favorites_shares。
"""Add favorites and immutable share links.

Revision ID: 0014_favorites_shares
Revises: 0013_itinerary_patches
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014_favorites_shares"
down_revision: str | None = "0013_itinerary_patches"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "favorites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.String(length=200), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_favorites_owner_kind_target",
        "favorites",
        ["owner_id", "kind", "target_id"],
        unique=True,
    )
    op.create_index(
        "ix_favorites_owner_created",
        "favorites",
        ["owner_id", "created_at"],
    )
    op.create_table(
        "share_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_share_links_token_hash",
        "share_links",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_share_links_trip_created",
        "share_links",
        ["trip_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_share_links_trip_created", table_name="share_links")
    op.drop_index("uq_share_links_token_hash", table_name="share_links")
    op.drop_table("share_links")
    op.drop_index("ix_favorites_owner_created", table_name="favorites")
    op.drop_index("uq_favorites_owner_kind_target", table_name="favorites")
    op.drop_table("favorites")
