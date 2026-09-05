"""健康计划与安全检查的数据契约。"""

from datetime import date
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class HealthPlanDraft(BaseModel):
    """Agent 生成、尚未持久化的健康计划。"""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    date: date
    exercise_plan: list[str] = Field(min_length=1)
    diet_plan: list[str] = Field(min_length=1)
    sleep_plan: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=2000)


class HealthPlan(HealthPlanDraft):
    """通过安全校验并已持久化的健康计划。"""

    id: str = Field(default_factory=lambda: str(uuid4()))


class SafetyValidation(BaseModel):
    """安全规则引擎的结构化检查结果。"""

    safe: bool
    issues: list[str] = Field(default_factory=list)

