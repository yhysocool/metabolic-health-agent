"""增加 vivo 一次性设备绑定码和设备级凭据。"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_0005"
down_revision: str | None = "20260904_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建设备绑定所需的最小服务端状态。"""

    op.create_table(
        "vivo_enrollment_codes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index(
        "ix_vivo_enrollment_codes_user_id",
        "vivo_enrollment_codes",
        ["user_id"],
    )
    op.create_table(
        "vivo_device_credentials",
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("credential_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("device_id"),
        sa.UniqueConstraint("credential_hash"),
    )
    op.create_index(
        "ix_vivo_device_credentials_user_id",
        "vivo_device_credentials",
        ["user_id"],
    )


def downgrade() -> None:
    """删除设备绑定状态。"""

    op.drop_index("ix_vivo_device_credentials_user_id", table_name="vivo_device_credentials")
    op.drop_table("vivo_device_credentials")
    op.drop_index("ix_vivo_enrollment_codes_user_id", table_name="vivo_enrollment_codes")
    op.drop_table("vivo_enrollment_codes")
