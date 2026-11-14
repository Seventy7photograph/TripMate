# 文件说明：数据库迁移：0029_route_cache_coordinates。
"""Add coordinate-aware route cache keys.

Revision ID: 0029_route_cache_coordinates
Revises: 0028_mcp_connectors
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029_route_cache_coordinates"
down_revision: str | None = "0028_mcp_connectors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "route_legs",
        sa.Column("coordinate_hash", sa.String(length=64), nullable=True),
    )
    # Existing rows intentionally receive a non-matching sentinel and expire
    # naturally instead of trusting a route computed from old coordinates.
    op.execute("UPDATE route_legs SET coordinate_hash = 'legacy'")
    op.alter_column(
        "route_legs",
        "coordinate_hash",
        nullable=False,
    )
    op.drop_index("uq_route_legs_day_pair_mode", table_name="route_legs")
    op.create_index(
        "uq_route_legs_day_pair_mode_coordinates",
        "route_legs",
        [
            "day_id",
            "from_stop_id",
            "to_stop_id",
            "mode",
            "coordinate_hash",
        ],
        unique=True,
    )


def downgrade() -> None:
    # Keep the newest route for each legacy key before restoring the old unique index.
    op.execute(
        """
        DELETE FROM route_legs stale
        USING route_legs current
        WHERE stale.day_id = current.day_id
          AND stale.from_stop_id = current.from_stop_id
          AND stale.to_stop_id = current.to_stop_id
          AND stale.mode = current.mode
          AND (stale.fetched_at, stale.id) < (current.fetched_at, current.id)
        """
    )
    op.drop_index(
        "uq_route_legs_day_pair_mode_coordinates",
        table_name="route_legs",
    )
    op.create_index(
        "uq_route_legs_day_pair_mode",
        "route_legs",
        ["day_id", "from_stop_id", "to_stop_id", "mode"],
        unique=True,
    )
    op.drop_column("route_legs", "coordinate_hash")
