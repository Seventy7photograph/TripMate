# 文件说明：数据库迁移：0021_trip_day_leg_modes。
"""Persist per-leg travel modes on trip days.

Revision ID: 0021_trip_day_leg_modes
Revises: 0020_remove_mock_weather_feature
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0021_trip_day_leg_modes"
down_revision: str | None = "0020_remove_mock_weather_feature"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trip_days",
        sa.Column(
            "leg_modes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("trip_days", "leg_modes")
