"""NHANES 公开数据适配器占位。当前版本不下载或解析真实数据。"""

from collections.abc import Sequence

from app.adapters.base import BaseHealthAdapter, RawHealthRecord
from app.schemas.health import HealthEventCreate


class NHANESAdapter(BaseHealthAdapter):
    """预留 NHANES 周期、问卷和实验室指标到统一事件的映射边界。"""

    def load_data(self, user_id: str) -> Sequence[RawHealthRecord]:
        raise NotImplementedError("基础架构阶段不下载 NHANES 数据")

    def normalize(
        self, user_id: str, records: Sequence[RawHealthRecord]
    ) -> list[HealthEventCreate]:
        raise NotImplementedError("需先定义 NHANES 字段与单位映射表")

