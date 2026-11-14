# 文件说明：数据库迁移：0027_external_fact_tools。
"""Add place reference price and altitude evidence type.

Revision ID: 0027_external_fact_tools
Revises: 0026_prompt_versions
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027_external_fact_tools"
down_revision: str | None = "0026_prompt_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "places",
        sa.Column("reference_price", sa.String(length=120), nullable=True),
    )
    op.drop_constraint(
        "ck_evidence_records_fact_type",
        "evidence_records",
        type_="check",
    )
    op.create_check_constraint(
        "ck_evidence_records_fact_type",
        "evidence_records",
        "fact_type IN ("
        "'place_fact', 'weather', 'transport', 'lodging_area', "
        "'meal', 'safety', 'altitude', 'attachment'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_evidence_records_fact_type",
        "evidence_records",
        type_="check",
    )
    op.create_check_constraint(
        "ck_evidence_records_fact_type",
        "evidence_records",
        "fact_type IN ("
        "'place_fact', 'weather', 'transport', 'lodging_area', "
        "'meal', 'safety', 'attachment'"
        ")",
    )
    op.drop_column("places", "reference_price")
