"""健康管理核心实体的 SQLAlchemy ORM 映射。"""

from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.schemas.health import HealthMetric, HealthSource
from app.schemas.integration import IntegrationProvider
from app.schemas.user import Gender, HealthGoal


def enum_values(enum_class: type[Enum]) -> list[str]:
    """让 SQLAlchemy 持久化枚举的业务值，而不是 Python 成员名。"""

    return [str(item.value) for item in enum_class]


class UserProfileModel(Base):
    """用户档案表；仅保存完成健康管理所需的字段。"""

    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[Gender] = mapped_column(
        SAEnum(
            Gender,
            values_callable=enum_values,
            name="gender_enum",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
    )
    height: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    bmi: Mapped[float] = mapped_column(Float, nullable=False)
    goal: Mapped[HealthGoal] = mapped_column(
        SAEnum(
            HealthGoal,
            values_callable=enum_values,
            name="health_goal_enum",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
    )


class HealthEventModel(Base):
    """统一健康事件表；外部数据必须先经 Adapter 标准化后才能写入。"""

    __tablename__ = "health_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source",
            "source_record_id",
            name="uq_health_events_source_record",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source: Mapped[HealthSource] = mapped_column(
        SAEnum(
            HealthSource,
            values_callable=enum_values,
            name="health_source_enum",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        nullable=False,
    )
    metric: Mapped[HealthMetric] = mapped_column(
        SAEnum(
            HealthMetric,
            values_callable=enum_values,
            name="health_metric_enum",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        index=True,
        nullable=False,
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    end_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provenance: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)


class IntegrationSyncStateModel(Base):
    """每个用户和数据提供方只保存一份最小增量同步状态。"""

    __tablename__ = "integration_sync_states"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[IntegrationProvider] = mapped_column(
        SAEnum(
            IntegrationProvider,
            values_callable=enum_values,
            name="integration_provider_enum",
            native_enum=False,
            create_constraint=True,
            length=32,
        ),
        primary_key=True,
    )
    device_id_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    cursor: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_success_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_record_count: Mapped[int] = mapped_column(Integer, nullable=False)


class VivoEnrollmentCodeModel(Base):
    """一次性设备绑定码；数据库只保存摘要，不保存可再次使用的明文。"""

    __tablename__ = "vivo_enrollment_codes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class VivoDeviceCredentialModel(Base):
    """设备绑定身份；公钥可公开，上传凭据只保存 SHA-256 摘要。"""

    __tablename__ = "vivo_device_credentials"

    device_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    credential_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class VivoCollectionRunModel(Base):
    """一次 Provider 采集运行的诊断摘要，不保存虚假的健康数值。"""

    __tablename__ = "vivo_collection_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_measured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_measured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_schema_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class HealthPlanModel(Base):
    """通过安全规则检查后保存的个性化健康计划。"""

    __tablename__ = "health_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    exercise_plan: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    diet_plan: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    sleep_plan: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
