"""生成由 NHANES 聚合值校准、且明确标记的本地演示事件。"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import random
from typing import Any

from app.adapters.base import BaseHealthAdapter, RawHealthRecord
from app.schemas.health import (
    HealthEventCreate,
    HealthEventProvenance,
    HealthMetric,
    HealthSource,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REFERENCE_PATH = (
    PROJECT_ROOT / "data" / "reference" / "nhanes_adult_30_39_reference_v1.json"
)
GENERATOR_VERSION = "1.0.0"


class SyntheticHealthAdapter(BaseHealthAdapter):
    """生成不对应任何真人、手表或单条 NHANES 记录的确定性演示数据。"""

    _units = {
        HealthMetric.SLEEP: "hour",
        HealthMetric.STEPS: "step",
        HealthMetric.HEART_RATE: "bpm",
        HealthMetric.EXERCISE: "minute",
    }

    def __init__(
        self,
        days: int = 30,
        seed: int = 42,
        reference_path: Path = DEFAULT_REFERENCE_PATH,
    ) -> None:
        if days < 1 or days > 365:
            raise ValueError("days 必须在 1 到 365 之间")
        self.days = days
        self.seed = seed
        self.reference_path = reference_path

    def _load_reference(self) -> dict[str, Any]:
        payload = json.loads(self.reference_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise ValueError("不支持的 NHANES 聚合参考文件版本")
        return payload

    def load_data(self, user_id: str) -> Sequence[RawHealthRecord]:
        reference = self._load_reference()
        metrics = reference["metrics"]
        sleep_reference = metrics["sleep_hours"]
        weekly_activity_reference = metrics["activity_equivalent_minutes_week"]
        rng = random.Random(self.seed)
        now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
        records: list[RawHealthRecord] = []

        for index, day_offset in enumerate(reversed(range(self.days))):
            timestamp = now - timedelta(days=day_offset)
            weekly_cycle = math.sin(index * math.tau / 7)
            sleep = min(
                float(sleep_reference["p75"]),
                max(
                    float(sleep_reference["p25"]),
                    float(sleep_reference["median"])
                    + weekly_cycle * 0.28
                    + rng.uniform(-0.32, 0.32),
                ),
            )
            exercise = max(
                8.0,
                min(
                    70.0,
                    float(weekly_activity_reference["median"]) / 14
                    + weekly_cycle * 8
                    + rng.uniform(-9, 9),
                ),
            )
            steps = max(3200.0, min(11800.0, 6100 + exercise * 52 + rng.uniform(-900, 900)))
            heart_rate = max(56.0, min(90.0, 75 - exercise * 0.08 + rng.uniform(-4, 4)))
            values = {
                HealthMetric.SLEEP: round(sleep, 2),
                HealthMetric.STEPS: float(round(steps)),
                HealthMetric.HEART_RATE: round(heart_rate, 1),
                HealthMetric.EXERCISE: float(round(exercise)),
            }
            for metric, value in values.items():
                records.append(
                    {
                        "metric": metric.value,
                        "value": value,
                        "unit": self._units[metric],
                        "timestamp": timestamp,
                        "source_record_id": f"demo-{timestamp.date().isoformat()}-{metric.value}",
                        "reference_id": reference["reference_id"],
                    }
                )
        return records

    def normalize(
        self, user_id: str, records: Sequence[RawHealthRecord]
    ) -> list[HealthEventCreate]:
        result: list[HealthEventCreate] = []
        for record in records:
            metric = HealthMetric(str(record["metric"]))
            uses_nhanes_reference = metric in {HealthMetric.SLEEP, HealthMetric.EXERCISE}
            result.append(
                HealthEventCreate(
                    user_id=user_id,
                    source=HealthSource.SYNTHETIC,
                    metric=metric,
                    value=float(record["value"]),
                    unit=str(record["unit"]),
                    timestamp=record["timestamp"],
                    source_record_id=str(record["source_record_id"]),
                    provenance=HealthEventProvenance(
                        display_label="本地合成演示数据",
                        is_synthetic=True,
                        reference_dataset="NHANES" if uses_nhanes_reference else None,
                        reference_version=(
                            str(record["reference_id"]) if uses_nhanes_reference else None
                        ),
                        generator_version=GENERATOR_VERSION,
                        note=(
                            "由 NHANES 30–39 岁聚合参考值校准，不对应任何调查参与者。"
                            if uses_nhanes_reference
                            else "本地规则生成；NHANES 未为本项目提供该穿戴设备时序指标。"
                        ),
                    ),
                )
            )
        return result
