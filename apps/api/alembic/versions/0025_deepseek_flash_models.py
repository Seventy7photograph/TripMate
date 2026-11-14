# 文件说明：数据库迁移：0025_deepseek_flash_models。
"""Replace legacy DeepSeek chat model configuration.

Revision ID: 0025_deepseek_flash_models
Revises: 0024_agent_skill_audit
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025_deepseek_flash_models"
down_revision: str | None = "0024_agent_skill_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE agent_model_configs "
            "SET model_name = 'deepseek-flash' "
            "WHERE model_name = 'deepseek-chat'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE agent_model_configs "
            "SET model_name = 'deepseek-chat' "
            "WHERE model_name = 'deepseek-flash'"
        )
    )
