"""用户档案的数据契约，只保存健康管理所需的最小字段。"""

from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Gender(str, Enum):
    """用户自述性别；允许不披露，避免强迫收集敏感信息。"""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNDISCLOSED = "undisclosed"


class HealthGoal(str, Enum):
    """当前首要健康管理目标。"""

    WEIGHT_MANAGEMENT = "weight_management"
    METABOLIC_HEALTH = "metabolic_health"
    SLEEP_IMPROVEMENT = "sleep_improvement"


class UserProfileBase(BaseModel):
    """用户档案公共字段。

    BMI 是派生值。调用方不提供时由身高、体重计算；调用方提供时也会重新计算，
    防止多个数据源产生不一致结果。
    """

    model_config = ConfigDict(from_attributes=True)

    age: int = Field(ge=18, le=120)
    gender: Gender = Gender.UNDISCLOSED
    height: float = Field(gt=0, le=260, description="身高，单位 cm")
    weight: float = Field(gt=0, le=500, description="体重，单位 kg")
    bmi: float | None = Field(default=None, gt=0, le=100)
    goal: HealthGoal

    @model_validator(mode="after")
    def calculate_consistent_bmi(self) -> "UserProfileBase":
        height_m = self.height / 100
        self.bmi = round(self.weight / (height_m * height_m), 2)
        return self


class UserProfileCreate(UserProfileBase):
    """创建用户档案时由客户端提交的字段。"""

    id: str = Field(default_factory=lambda: str(uuid4()))


class UserProfile(UserProfileBase):
    """已持久化的用户档案。"""

    id: str

