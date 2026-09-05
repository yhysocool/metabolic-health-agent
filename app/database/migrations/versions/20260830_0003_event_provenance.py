"""为统一健康事件增加可展示的数据来源说明。"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260830_0003"
down_revision: str | None = "20260824_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """以可空 JSON 列兼容已有事件。"""

    op.drop_constraint("health_source_enum", "health_events", type_="check")
    op.create_check_constraint(
        "health_source_enum",
        "health_events",
        "source IN ('mock', 'synthetic', 'manual', 'nhanes', 'vivo', 'hospital')",
    )
    op.add_column("health_events", sa.Column("provenance", sa.JSON(), nullable=True))


def downgrade() -> None:
    """移除事件来源说明。"""

    op.drop_column("health_events", "provenance")
    op.drop_constraint("health_source_enum", "health_events", type_="check")
    op.create_check_constraint(
        "health_source_enum",
        "health_events",
        "source IN ('mock', 'nhanes', 'vivo', 'hospital')",
    )
