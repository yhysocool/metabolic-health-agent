"""外部健康数据同步契约；不依赖任何厂商 SDK 对象。"""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.health import HealthMetric


class IntegrationProvider(str, Enum):
    """当前允许进入同步状态表的数据提供方。"""

    VIVO = "vivo"


class HealthRecordStatus(str, Enum):
    """设备侧读取结果；只有 PASS 记录进入数值事件表。"""

    PASS = "PASS"
    NO_DATA = "NO_DATA"
    DENIED = "DENIED"
    UNSUPPORTED = "UNSUPPORTED"
    ERROR = "ERROR"


class VivoBridgeRecord(BaseModel):
    """Android 桥接层向后端提交的项目自有中间格式。

    字段名不冒充 vivo Health Kit 的官方 DTO；桥接层负责把获授权的 SDK
    数据转换为本格式，后端再通过 Adapter 做单位和事件模型归一化。
    """

    record_id: str = Field(min_length=1, max_length=128)
    metric: HealthMetric
    value: float
    unit: str = Field(min_length=1, max_length=32)
    source: str = Field(default="vivo_local_health_provider", min_length=1, max_length=128)
    source_device: str = Field(default="vivo_health_provider", min_length=1, max_length=128)
    measured_at: datetime | None = None
    start_time: datetime
    end_time: datetime | None = None
    status: HealthRecordStatus = HealthRecordStatus.PASS
    raw_source: str = Field(default="vivo_bridge", min_length=1, max_length=256)
    synced_at: datetime | None = None

    @field_validator("measured_at", "start_time", "end_time", "synced_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("vivo 同步时间必须包含时区")
        return value

    @model_validator(mode="after")
    def validate_interval(self) -> "VivoBridgeRecord":
        if self.end_time is not None and self.end_time < self.start_time:
            raise ValueError("end_time 不能早于 start_time")
        if self.status != HealthRecordStatus.PASS:
            raise ValueError("只有 PASS 且包含真实数值的记录可以写入健康事件表")
        return self


class VivoCollectionRun(BaseModel):
    """一次设备采集运行的可审计摘要。"""

    run_id: str = Field(min_length=1, max_length=64)
    source: str = Field(default="vivo_phone", min_length=1, max_length=128)
    read_at: datetime
    status: HealthRecordStatus
    provider_row_count: int = Field(ge=0, le=100000)
    valid_record_count: int = Field(ge=0, le=100000)
    first_measured_at: datetime | None = None
    last_measured_at: datetime | None = None
    app_version: str | None = Field(default=None, max_length=32)
    provider_schema_hash: str | None = Field(default=None, min_length=64, max_length=64)

    @field_validator(
        "read_at",
        "first_measured_at",
        "last_measured_at",
    )
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("采集运行时间必须包含时区")
        return value

    @model_validator(mode="after")
    def validate_measurement_range(self) -> "VivoCollectionRun":
        if (
            self.first_measured_at is not None
            and self.last_measured_at is not None
            and self.last_measured_at < self.first_measured_at
        ):
            raise ValueError("last_measured_at 不能早于 first_measured_at")
        # provider_row_count 统计 Provider 原始行，valid_record_count 统计归一化后的
        # 健康记录。一个 Provider 行可能包含多个指标（例如心率、血氧和压力），
        # 因此归一化记录数合法地可以大于原始行数。
        return self


class VivoSyncRequest(BaseModel):
    """单次增量同步请求；每条记录必须带稳定的来源记录 ID。"""

    batch_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)
    device_id: str = Field(min_length=1, max_length=256)
    cursor: str | None = Field(default=None, max_length=512)
    collection_runs: list[VivoCollectionRun] = Field(default_factory=list, max_length=1000)
    records: list[VivoBridgeRecord] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def require_records_or_runs(self) -> "VivoSyncRequest":
        if not self.records and not self.collection_runs:
            raise ValueError("同步请求至少需要包含健康记录或采集运行记录")
        return self


class EventSyncCounts(BaseModel):
    """仓储原子提交后返回的幂等写入统计。"""

    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    unchanged: int = Field(ge=0)


class IntegrationSyncState(BaseModel):
    """服务端保存的最小同步状态；设备标识只保留 SHA-256 摘要。"""

    user_id: str = Field(min_length=1, max_length=64)
    provider: IntegrationProvider
    device_id_hash: str = Field(min_length=64, max_length=64)
    cursor: str | None = Field(default=None, max_length=512)
    last_success_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_record_count: int = Field(ge=0)


class VivoSyncResult(BaseModel):
    """vivo 同步 API 的非敏感响应。"""

    batch_id: str
    user_id: str
    provider: IntegrationProvider = IntegrationProvider.VIVO
    received: int = Field(ge=0)
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    cursor: str | None = None
    last_success_at: datetime
    collection_runs_received: int = Field(default=0, ge=0)
    collection_runs_created: int = Field(default=0, ge=0)


class VivoSyncStatus(BaseModel):
    """Dashboard 可查询的同步状态，不返回设备原始标识。"""

    user_id: str
    provider: IntegrationProvider = IntegrationProvider.VIVO
    connected: bool
    cursor: str | None = None
    last_success_at: datetime | None = None
    last_record_count: int = Field(default=0, ge=0)


class VivoEnrollmentCodeRequest(BaseModel):
    """管理员为已存在的用户生成一次性设备绑定码。"""

    user_id: str = Field(min_length=1, max_length=64)
    expires_in_minutes: int = Field(default=10, ge=1, le=60)


class VivoEnrollmentCodeResponse(BaseModel):
    """管理员交给二维码生成器的短期绑定载荷。"""

    user_id: str
    code: str
    payload: str
    expires_at: datetime


class VivoDeviceEnrollmentRequest(BaseModel):
    """Android 设备使用一次性绑定码证明私钥持有并注册公钥。"""

    enrollment_code: str = Field(min_length=16, max_length=128)
    device_id: str = Field(
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    public_key: str = Field(min_length=32, max_length=4096)
    proof: str = Field(min_length=16, max_length=4096)


class VivoDeviceEnrollmentResponse(BaseModel):
    """仅通过 HTTPS 返回一次的设备级同步凭据；不会在状态接口回显。"""

    device_id: str
    user_id: str
    sync_token: str = Field(min_length=32)
