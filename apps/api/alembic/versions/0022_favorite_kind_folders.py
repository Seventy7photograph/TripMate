# 文件说明：数据库迁移：0022_favorite_kind_folders。
"""Rename legacy default favorite folders by kind.

Revision ID: 0022_favorite_kind_folders
Revises: 0021_trip_day_leg_modes
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022_favorite_kind_folders"
down_revision: str | None = "0021_trip_day_leg_modes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE favorites SET folder = '地点收藏' "
            "WHERE kind = 'place' AND folder = '默认收藏'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE favorites SET folder = '行程收藏' "
            "WHERE kind = 'trip' AND folder = '默认收藏'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE favorites SET folder = '默认收藏' "
            "WHERE kind = 'place' AND folder = '地点收藏'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE favorites SET folder = '默认收藏' "
            "WHERE kind = 'trip' AND folder = '行程收藏'"
        )
    )
