# 文件说明：数据库迁移：0026_prompt_versions。
"""Add AgentRun prompt version audit records.

Revision ID: 0026_prompt_versions
Revises: 0025_deepseek_flash_models
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0026_prompt_versions"
down_revision: str | None = "0025_deepseek_flash_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column(
            "prompt_versions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "prompt_versions")
