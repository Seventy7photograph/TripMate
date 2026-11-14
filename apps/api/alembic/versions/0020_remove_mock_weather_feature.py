# 文件说明：数据库迁移：0020_remove_mock_weather_feature。
"""Remove the unimplemented mock weather feature.

Revision ID: 0020_remove_mock_weather_feature
Revises: 0019_favorite_organization
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_remove_mock_weather_feature"
down_revision: str | None = "0019_favorite_organization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("DELETE FROM feature_flags WHERE key = 'weather_provider'")
    )


def downgrade() -> None:
    feature_flags = sa.table(
        "feature_flags",
        sa.column("key", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("description", sa.Text()),
    )
    op.execute(
        feature_flags.insert().values(
            key="weather_provider",
            enabled=True,
            description="天气 Provider：允许天气和穿衣建议数据调用",
        )
    )
