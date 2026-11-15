# 文件说明：数据库迁移：0031_conversation_planning_draft。
"""Add structured planning draft to conversations.

Revision ID: 0031_conversation_planning_draft
Revises: 0030_user_token_version
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0031_conversation_planning_draft"
down_revision: str | None = "0030_user_token_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "planning_draft",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "planning_draft")
