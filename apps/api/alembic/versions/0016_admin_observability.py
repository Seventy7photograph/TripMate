# 文件说明：数据库迁移：0016_admin_observability。
"""Add admin roles, feature controls and provider observability.

Revision ID: 0016_admin_observability
Revises: 0015_user_memories
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016_admin_observability"
down_revision: str | None = "0015_user_memories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FEATURE_FLAGS = (
    (
        "ai_planning",
        "AI 行程规划",
        "允许创建新的 LangGraph 规划任务",
    ),
    (
        "brief_parsing",
        "旅行需求解析",
        "允许调用 LLM 解析自然语言旅行需求",
    ),
    (
        "llm_provider",
        "LLM Provider",
        "允许调用已配置的语言模型 Provider",
    ),
    (
        "map_provider",
        "地图 Provider",
        "允许地点搜索、地理编码和路线计算",
    ),
    (
        "weather_provider",
        "天气 Provider",
        "允许天气和穿衣建议数据调用",
    ),
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=16),
            server_default=sa.text("'user'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('user', 'admin')",
    )
    op.add_column(
        "agent_runs",
        sa.Column("request_ip_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_agent_runs_ip_created",
        "agent_runs",
        ["request_ip_hash", "created_at"],
    )

    feature_flags = op.create_table(
        "feature_flags",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("key"),
    )
    op.bulk_insert(
        feature_flags,
        [
            {
                "key": key,
                "enabled": True,
                "description": f"{label}：{description}",
            }
            for key, label, description in FEATURE_FLAGS
        ],
    )

    op.create_table(
        "provider_health",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("provider_type", sa.String(length=24), nullable=False),
        sa.Column("provider_name", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_key"),
    )
    op.create_index(
        "ix_provider_health_type_checked",
        "provider_health",
        ["provider_type", "checked_at"],
    )

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=120), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_audit_logs_actor_created",
        "admin_audit_logs",
        ["actor_id", "created_at"],
    )
    op.create_index(
        "ix_admin_audit_logs_action_created",
        "admin_audit_logs",
        ["action", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_audit_logs_action_created",
        table_name="admin_audit_logs",
    )
    op.drop_index(
        "ix_admin_audit_logs_actor_created",
        table_name="admin_audit_logs",
    )
    op.drop_table("admin_audit_logs")
    op.drop_index("ix_provider_health_type_checked", table_name="provider_health")
    op.drop_table("provider_health")
    op.drop_table("feature_flags")
    op.drop_index("ix_agent_runs_ip_created", table_name="agent_runs")
    op.drop_column("agent_runs", "request_ip_hash")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
