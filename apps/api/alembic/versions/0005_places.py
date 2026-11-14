# 文件说明：数据库迁移：0005_places。
"""Create place cache tables.

Revision ID: 0005_places
Revises: 0004_trip_versions
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_places"
down_revision: str | None = "0004_trip_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "places",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_place_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=200), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("coordinate_system", sa.String(length=16), nullable=True),
        sa.Column("tel", sa.String(length=80), nullable=True),
        sa.Column(
            "opening_hours",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "source",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_places_provider_place",
        "places",
        ["provider", "provider_place_id"],
        unique=True,
    )
    op.create_index(
        "ix_places_provider_name",
        "places",
        ["provider", "name"],
        unique=False,
    )

    op.create_table(
        "place_search_cache",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("query_text", sa.String(length=500), nullable=False),
        sa.Column(
            "results",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_place_search_provider_query",
        "place_search_cache",
        ["provider", "query_hash"],
        unique=True,
    )
    op.create_index(
        "ix_place_search_expires",
        "place_search_cache",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_place_search_expires", table_name="place_search_cache")
    op.drop_index(
        "uq_place_search_provider_query",
        table_name="place_search_cache",
    )
    op.drop_table("place_search_cache")
    op.drop_index("ix_places_provider_name", table_name="places")
    op.drop_index("uq_places_provider_place", table_name="places")
    op.drop_table("places")
