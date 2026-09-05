"""人群参照数据的只读领域接口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


ReferenceStatus = Literal["PASS", "NO_DATA"]


@dataclass(frozen=True)
class PopulationReference:
    """一个年龄段、性别和指标对应的聚合参照。"""

    reference_id: str
    source: str
    metric_code: str
    unit: str
    age_band: str
    age_min: int
    age_max: int
    gender: str
    records: int
    statistics: dict[str, float | int | None]
    status: ReferenceStatus
    note: str


class PopulationReferenceRepository(Protocol):
    """业务层依赖的只读人群参照协议，不暴露个体记录。"""

    def get_statistic(
        self, *, age: int, gender: str, metric_code: str
    ) -> PopulationReference | None:
        """按精确年龄段、性别和指标查询聚合统计。"""
