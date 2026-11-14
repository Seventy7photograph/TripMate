# 文件说明：数据库迁移：0003_itinerary。
"""Create itinerary tables.

Revision ID: 0003_itinerary
Revises: 0002_trips
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_itinerary"
down_revision: str | None = "0002_trips"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trip_days",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("day_index", sa.Integer(), nullable=False),
        sa.Column("theme", sa.String(length=160), nullable=True),
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
        sa.CheckConstraint("day_index > 0", name="ck_trip_days_day_index"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_trip_days_trip_date",
        "trip_days",
        ["trip_id", "date"],
        unique=True,
    )
    op.create_index(
        "ix_trip_days_trip_date",
        "trip_days",
        ["trip_id", "date"],
        unique=False,
    )

    op.create_table(
        "itinerary_stops",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("day_id", sa.Uuid(), nullable=False),
        sa.Column("place_id", sa.String(length=200), nullable=False),
        sa.Column("place_name", sa.String(length=200), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_minor", sa.Integer(), nullable=False),
        sa.Column(
            "source",
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
            "duration_minutes > 0 AND duration_minutes <= 1440",
            name="ck_itinerary_stops_duration",
        ),
        sa.CheckConstraint(
            "estimated_cost_minor >= 0",
            name="ck_itinerary_stops_cost",
        ),
        sa.CheckConstraint("order_index >= 0", name="ck_itinerary_stops_order"),
        sa.ForeignKeyConstraint(["day_id"], ["trip_days.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_itinerary_stops_day_order",
        "itinerary_stops",
        ["day_id", "order_index"],
        unique=True,
    )
    op.create_index(
        "ix_itinerary_stops_day_order",
        "itinerary_stops",
        ["day_id", "order_index"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_itinerary_stops_day_order", table_name="itinerary_stops")
    op.drop_index("uq_itinerary_stops_day_order", table_name="itinerary_stops")
    op.drop_table("itinerary_stops")
    op.drop_index("ix_trip_days_trip_date", table_name="trip_days")
    op.drop_index("uq_trip_days_trip_date", table_name="trip_days")
    op.drop_table("trip_days")
