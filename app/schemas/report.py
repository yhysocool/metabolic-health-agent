"""健康数据质量报告的数据契约。"""

from datetime import datetime

from pydantic import BaseModel, Field


class MetricQualitySummary(BaseModel):
    """单个指标在回看窗口内的观测覆盖摘要。"""

    metric: str
    unit: str
    records: int = Field(ge=0)
    covered_days: int = Field(ge=0)
    first_at: datetime | None = None
    last_at: datetime | None = None
    min_value: float | None = None
    average_value: float | None = None
    max_value: float | None = None
    zero_value_count: int = Field(default=0, ge=0)


class DataQualityReport(BaseModel):
    """面向用户的可解释数据覆盖和同步质量报告。"""

    user_id: str
    window_days: int = Field(ge=1, le=365)
    generated_at: datetime
    event_count: int = Field(ge=0)
    coverage_days: int = Field(ge=0)
    first_event_at: datetime | None = None
    last_event_at: datetime | None = None
    collection_run_count: int = Field(ge=0)
    collection_status_counts: dict[str, int]
    provider_rows: int = Field(ge=0)
    valid_records: int = Field(ge=0)
    last_sync_at: datetime | None = None
    metrics: list[MetricQualitySummary]
    notices: list[str]
    disclaimer: str = "本报告仅描述数据覆盖和趋势基础，不构成医疗诊断或治疗建议。"
