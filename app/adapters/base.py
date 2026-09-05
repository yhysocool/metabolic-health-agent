"""健康数据 Adapter 的抽象接口与公共校验。"""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
import math

from app.schemas.health import HealthEventCreate


RawHealthRecord = Mapping[str, object]


class BaseHealthAdapter(ABC):
    """所有数据来源必须实现的三阶段入口。

    ``load_data`` 只读取源数据，``normalize`` 转换为统一事件，``validate``
    在入库前执行来源无关的完整性检查。真实 Adapter 后续可追加来源特有校验。
    """

    @abstractmethod
    def load_data(self, user_id: str) -> Sequence[RawHealthRecord]:
        """读取原始记录，不在此阶段写入数据库。"""

    @abstractmethod
    def normalize(
        self, user_id: str, records: Sequence[RawHealthRecord]
    ) -> list[HealthEventCreate]:
        """将来源字段映射到统一健康事件。"""

    def validate(self, events: Sequence[HealthEventCreate]) -> None:
        """执行最低限度的数据质量检查，失败时拒绝整批数据。"""

        for event in events:
            if not math.isfinite(event.value):
                raise ValueError(f"指标 {event.metric.value} 的值不是有限数")
            if event.value < 0:
                raise ValueError(f"指标 {event.metric.value} 不允许为负数")

    def collect(self, user_id: str) -> list[HealthEventCreate]:
        """按固定顺序执行读取、标准化和校验。"""

        events = self.normalize(user_id, self.load_data(user_id))
        self.validate(events)
        return events

