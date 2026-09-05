"""创建用户档案、统一健康事件和健康计划表。"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260821_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建首版稳定数据结构及常用查询索引。"""

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("gender", sa.String(length=32), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("bmi", sa.Float(), nullable=False),
        sa.Column("goal", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "gender IN ('male', 'female', 'other', 'undisclosed')",
            name="gender_enum",
        ),
        sa.CheckConstraint(
            "goal IN ('weight_management', 'metabolic_health', 'sleep_improvement')",
            name="health_goal_enum",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "health_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("metric", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source IN ('mock', 'nhanes', 'vivo', 'hospital')",
            name="health_source_enum",
        ),
        sa.CheckConstraint(
            "metric IN ('sleep', 'steps', 'heart_rate', 'blood_glucose', "
            "'insulin', 'weight', 'bmi', 'exercise')",
            name="health_metric_enum",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_health_events_user_id", "health_events", ["user_id"])
    op.create_index("ix_health_events_metric", "health_events", ["metric"])
    op.create_index("ix_health_events_timestamp", "health_events", ["timestamp"])

    op.create_table(
        "health_plans",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("exercise_plan", sa.JSON(), nullable=False),
        sa.Column("diet_plan", sa.JSON(), nullable=False),
        sa.Column("sleep_plan", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_health_plans_user_id", "health_plans", ["user_id"])
    op.create_index("ix_health_plans_date", "health_plans", ["date"])


def downgrade() -> None:
    """按依赖关系逆序移除首版结构。"""

    op.drop_index("ix_health_plans_date", table_name="health_plans")
    op.drop_index("ix_health_plans_user_id", table_name="health_plans")
    op.drop_table("health_plans")
    op.drop_index("ix_health_events_timestamp", table_name="health_events")
    op.drop_index("ix_health_events_metric", table_name="health_events")
    op.drop_index("ix_health_events_user_id", table_name="health_events")
    op.drop_table("health_events")
    op.drop_table("user_profiles")
