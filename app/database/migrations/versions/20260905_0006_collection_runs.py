"""增加 vivo 采集运行摘要表。"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260905_0006"
down_revision: str | None = "20260904_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """保存 Provider 采集状态和覆盖摘要。"""

    op.create_table(
        "vivo_collection_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("device_id_hash", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider_row_count", sa.Integer(), nullable=False),
        sa.Column("valid_record_count", sa.Integer(), nullable=False),
        sa.Column("first_measured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_measured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("app_version", sa.String(length=32), nullable=True),
        sa.Column("provider_schema_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_vivo_collection_runs_user_id",
        "vivo_collection_runs",
        ["user_id"],
    )
    op.create_index(
        "ix_vivo_collection_runs_read_at",
        "vivo_collection_runs",
        ["read_at"],
    )


def downgrade() -> None:
    """删除采集运行摘要表。"""

    op.drop_index("ix_vivo_collection_runs_read_at", table_name="vivo_collection_runs")
    op.drop_index("ix_vivo_collection_runs_user_id", table_name="vivo_collection_runs")
    op.drop_table("vivo_collection_runs")
