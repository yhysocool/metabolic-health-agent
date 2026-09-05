"""医院脱敏体检数据适配器占位。当前版本不连接医院系统。"""

from collections.abc import Sequence

from app.adapters.base import BaseHealthAdapter, RawHealthRecord
from app.schemas.health import HealthEventCreate


class HospitalAdapter(BaseHealthAdapter):
    """预留脱敏、字段映射、数据授权和审计校验边界。"""

    def load_data(self, user_id: str) -> Sequence[RawHealthRecord]:
        raise NotImplementedError("基础架构阶段不接入任何医院数据")

    def normalize(
        self, user_id: str, records: Sequence[RawHealthRecord]
    ) -> list[HealthEventCreate]:
        raise NotImplementedError("需先完成医院字段字典和合规评审")

