"""人群参照查询的 API 数据契约。"""

from pydantic import BaseModel, ConfigDict, Field


class ReferenceStatistics(BaseModel):
    """单个分层的描述统计；无观测值时统计字段为 null。"""

    model_config = ConfigDict(extra="forbid")

    observed: int = Field(ge=0)
    missing: int = Field(ge=0)
    mean: float | None = None
    stddev: float | None = None
    min: float | None = None
    p25: float | None = None
    median: float | None = None
    p75: float | None = None
    max: float | None = None


class NHANESReferenceResponse(BaseModel):
    """主项目可以读取的聚合参照，不含 NHANES 个体标识。"""

    model_config = ConfigDict(extra="forbid")

    reference_id: str
    source: str
    metric_code: str
    unit: str
    age_band: str
    age_min: int
    age_max: int
    gender: str
    records: int = Field(ge=0)
    statistics: ReferenceStatistics
    status: str
    note: str
