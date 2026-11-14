# 文件说明：数据库迁移：0011_planning_queue_checkpoint。
"""Add planning queue metadata.

Revision ID: 0011_planning_queue_checkpoint
Revises: 0010_planning_graph_metrics
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_planning_queue_checkpoint"
down_revision: str | None = "0010_planning_graph_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column(
            "source_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "apply_to_itinerary",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "apply_to_itinerary")
    op.drop_column("agent_runs", "source_version")
