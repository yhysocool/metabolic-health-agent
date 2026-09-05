"""生成可重复的 30 天 Mock 健康事件。"""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
import random

from app.adapters.base import BaseHealthAdapter, RawHealthRecord
from app.schemas.health import HealthEventCreate, HealthMetric, HealthSource


class MockHealthAdapter(BaseHealthAdapter):
    """用于开发演示和自动化测试的确定性数据源。

    同一随机种子会产生一致的数据分布，便于回归测试；这些记录不对应任何真实用户。
    """

    _units = {
        HealthMetric.SLEEP: "hour",
        HealthMetric.STEPS: "step",
        HealthMetric.HEART_RATE: "bpm",
        HealthMetric.EXERCISE: "minute",
    }

    def __init__(self, days: int = 30, seed: int = 42) -> None:
        self.days = days
        self.seed = seed

    def load_data(self, user_id: str) -> Sequence[RawHealthRecord]:
        rng = random.Random(self.seed)
        now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
        records: list[RawHealthRecord] = []
        for day_offset in reversed(range(self.days)):
            timestamp = now - timedelta(days=day_offset)
            values = {
                HealthMetric.SLEEP: round(rng.uniform(6.2, 8.3), 2),
                HealthMetric.STEPS: float(rng.randint(4500, 10500)),
                HealthMetric.HEART_RATE: round(rng.uniform(62, 82), 1),
                HealthMetric.EXERCISE: float(rng.randint(10, 55)),
            }
            for metric, value in values.items():
                records.append(
                    {
                        "user_id": user_id,
                        "metric": metric.value,
                        "value": value,
                        "unit": self._units[metric],
                        "timestamp": timestamp,
                    }
                )
        return records

    def normalize(
        self, user_id: str, records: Sequence[RawHealthRecord]
    ) -> list[HealthEventCreate]:
        return [
            HealthEventCreate(
                user_id=user_id,
                source=HealthSource.MOCK,
                metric=HealthMetric(str(record["metric"])),
                value=float(record["value"]),
                unit=str(record["unit"]),
                timestamp=record["timestamp"],
            )
            for record in records
        ]

