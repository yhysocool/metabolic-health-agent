"""增加 vivo 增量同步所需的来源唯一键和同步状态。"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_0002"
down_revision: str | None = "20260821_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """扩展统一事件并创建最小化同步状态表。"""

    op.add_column(
        "health_events",
        sa.Column("end_timestamp", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "health_events",
        sa.Column("source_record_id", sa.String(length=128), nullable=True),
    )
    op.create_unique_constraint(
        "uq_health_events_source_record",
        "health_events",
        ["user_id", "source", "source_record_id"],
    )
    op.create_table(
        "integration_sync_states",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("device_id_hash", sa.String(length=64), nullable=False),
        sa.Column("cursor", sa.String(length=512), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_record_count", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "provider IN ('vivo')",
            name="integration_provider_enum",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "provider"),
    )


def downgrade() -> None:
    """移除同步状态和统一事件扩展字段。"""

    op.drop_table("integration_sync_states")
    op.drop_constraint(
        "uq_health_events_source_record", "health_events", type_="unique"
    )
    op.drop_column("health_events", "source_record_id")
    op.drop_column("health_events", "end_timestamp")
