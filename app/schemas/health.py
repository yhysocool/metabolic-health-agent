"""统一健康事件及健康状态输出的数据契约。"""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HealthSource(str, Enum):
    """健康事件允许的数据来源。"""

    MOCK = "mock"
    SYNTHETIC = "synthetic"
    MANUAL = "manual"
    NHANES = "nhanes"
    VIVO = "vivo"
    HOSPITAL = "hospital"


class HealthMetric(str, Enum):
    """第一阶段统一支持的健康指标。"""

    SLEEP = "sleep"
    SLEEP_TOTAL_DURATION = "sleep_total_duration"
    SLEEP_NIGHT_DURATION = "sleep_night_duration"
    SLEEP_NAP_DURATION = "sleep_nap_duration"
    SLEEP_LIGHT_DURATION = "sleep_light_duration"
    SLEEP_DEEP_DURATION = "sleep_deep_duration"
    SLEEP_REM_DURATION = "sleep_rem_duration"
    SLEEP_AWAKE_DURATION = "sleep_awake_duration"
    SLEEP_SCORE = "sleep_score"
    SLEEP_DEEP_CONTINUITY = "sleep_deep_continuity"
    SLEEP_AWAKE_EPISODE_COUNT = "sleep_awake_episode_count"
    SLEEP_AWAKE_EPISODE_DURATION = "sleep_awake_episode_duration"
    STEPS = "steps"
    DISTANCE = "distance"
    CALORIES = "calories"
    HEART_RATE = "heart_rate"
    HEART_RATE_RESTING = "heart_rate_resting"
    SPO2 = "spo2"
    STRESS = "stress"
    BLOOD_GLUCOSE = "blood_glucose"
    INSULIN = "insulin"
    WEIGHT = "weight"
    BMI = "bmi"
    EXERCISE = "exercise"


class HealthLabel(str, Enum):
    """非诊断性的健康关注等级。"""

    NORMAL = "normal"
    ATTENTION = "attention"
    HIGH_ATTENTION = "high_attention"


class TrendDirection(str, Enum):
    """趋势分析的统一输出。"""

    INCREASE = "increase"
    DECREASE = "decrease"
    STABLE = "stable"


class HealthEventProvenance(BaseModel):
    """健康事件的数据来源说明，供 API 和界面如实展示。"""

    model_config = ConfigDict(extra="forbid")

    display_label: str = Field(min_length=1, max_length=64)
    is_synthetic: bool = False
    reference_dataset: str | None = Field(default=None, max_length=64)
    reference_version: str | None = Field(default=None, max_length=64)
    generator_version: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=256)
    source_system: str | None = Field(default=None, max_length=128)
    source_device: str | None = Field(default=None, max_length=128)
    source_status: str | None = Field(default=None, max_length=32)
    raw_source: str | None = Field(default=None, max_length=256)
    synced_at: str | None = Field(default=None, max_length=64)


class HealthEventBase(BaseModel):
    """来自任意 Adapter 的标准健康事件。"""

    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(min_length=1, max_length=64)
    source: HealthSource
    metric: HealthMetric
    value: float
    unit: str = Field(min_length=1, max_length=32)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_timestamp: datetime | None = None
    source_record_id: str | None = Field(default=None, min_length=1, max_length=128)
    provenance: HealthEventProvenance | None = None

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """统一转换为带时区时间，避免跨数据源比较时产生歧义。"""

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @field_validator("end_timestamp")
    @classmethod
    def normalize_optional_timezone(cls, value: datetime | None) -> datetime | None:
        """可选结束时间与事件时间采用相同的时区规则。"""

        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @model_validator(mode="after")
    def validate_interval(self) -> "HealthEventBase":
        """区间事件的结束时间不能早于开始时间。"""

        if self.end_timestamp is not None and self.end_timestamp < self.timestamp:
            raise ValueError("end_timestamp 不能早于 timestamp")
        if self.source == HealthSource.SYNTHETIC:
            if self.provenance is None or not self.provenance.is_synthetic:
                raise ValueError("synthetic 事件必须携带 is_synthetic=true 的来源说明")
        if self.provenance is not None and self.provenance.is_synthetic:
            if self.source != HealthSource.SYNTHETIC:
                raise ValueError("只有 synthetic 来源可以标记为合成数据")
        return self


class HealthEventCreate(HealthEventBase):
    """上传健康事件的请求体。"""


class HealthEvent(HealthEventBase):
    """已持久化的健康事件。"""

    id: str = Field(default_factory=lambda: str(uuid4()))


class HealthEventList(BaseModel):
    """指定回看窗口内的健康事件集合。"""

    user_id: str
    window_days: int = Field(ge=1, le=365)
    count: int = Field(ge=0)
    items: list[HealthEvent]


class HealthStatus(BaseModel):
    """健康分析服务的可解释、非诊断输出。"""

    user_id: str
    score: float = Field(ge=0, le=100)
    label: HealthLabel
    bmi: float
    homa_ir: float | None = None
    trends: dict[str, TrendDirection]
    observations: list[str]
    data_notice: str
    disclaimer: str = "本结果仅用于健康管理参考，不构成医疗诊断或治疗建议。"
