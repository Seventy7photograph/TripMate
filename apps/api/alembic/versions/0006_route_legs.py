# 文件说明：数据库迁移：0006_route_legs。
"""Add stop coordinates and route legs.

Revision ID: 0006_route_legs
Revises: 0005_places
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_route_legs"
down_revision: str | None = "0005_places"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("itinerary_stops", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("itinerary_stops", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column(
        "itinerary_stops",
        sa.Column("coordinate_system", sa.String(length=16), nullable=True),
    )

    op.create_table(
        "route_legs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("day_id", sa.Uuid(), nullable=False),
        sa.Column("from_stop_id", sa.Uuid(), nullable=False),
        sa.Column("to_stop_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("polyline", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["day_id"], ["trip_days.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["from_stop_id"],
            ["itinerary_stops.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_stop_id"],
            ["itinerary_stops.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_route_legs_day_pair_mode",
        "route_legs",
        ["day_id", "from_stop_id", "to_stop_id", "mode"],
        unique=True,
    )
    op.create_index("ix_route_legs_day", "route_legs", ["day_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_route_legs_day", table_name="route_legs")
    op.drop_index("uq_route_legs_day_pair_mode", table_name="route_legs")
    op.drop_table("route_legs")
    op.drop_column("itinerary_stops", "coordinate_system")
    op.drop_column("itinerary_stops", "latitude")
    op.drop_column("itinerary_stops", "longitude")
