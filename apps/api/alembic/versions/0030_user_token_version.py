# 文件说明：数据库迁移：0030_user_token_version。
"""Add user token version for access-token revocation.

Revision ID: 0030_user_token_version
Revises: 0029_route_cache_coordinates
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0030_user_token_version"
down_revision: str | None = "0029_route_cache_coordinates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
