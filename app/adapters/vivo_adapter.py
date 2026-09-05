"""vivo Android 桥接数据适配器；当前版本不直接连接真实设备。"""

from collections.abc import Sequence

from app.adapters.base import BaseHealthAdapter, RawHealthRecord
from app.schemas.health import (
    HealthEventCreate,
    HealthEventProvenance,
    HealthMetric,
    HealthSource,
)
from app.schemas.integration import VivoBridgeRecord


class VivoAdapter(BaseHealthAdapter):
    """把项目自有桥接格式归一化为统一健康事件。"""

    _supported_metrics = {
        HealthMetric.STEPS,
        HealthMetric.DISTANCE,
        HealthMetric.CALORIES,
        HealthMetric.HEART_RATE,
        HealthMetric.HEART_RATE_RESTING,
        HealthMetric.SPO2,
        HealthMetric.STRESS,
        HealthMetric.SLEEP,
        HealthMetric.SLEEP_TOTAL_DURATION,
        HealthMetric.SLEEP_NIGHT_DURATION,
        HealthMetric.SLEEP_NAP_DURATION,
        HealthMetric.SLEEP_LIGHT_DURATION,
        HealthMetric.SLEEP_DEEP_DURATION,
        HealthMetric.SLEEP_REM_DURATION,
        HealthMetric.SLEEP_AWAKE_DURATION,
        HealthMetric.SLEEP_SCORE,
        HealthMetric.SLEEP_DEEP_CONTINUITY,
        HealthMetric.SLEEP_AWAKE_EPISODE_COUNT,
        HealthMetric.SLEEP_AWAKE_EPISODE_DURATION,
        HealthMetric.EXERCISE,
    }
    _duration_metrics = {
        HealthMetric.SLEEP,
        HealthMetric.SLEEP_TOTAL_DURATION,
        HealthMetric.SLEEP_NIGHT_DURATION,
        HealthMetric.SLEEP_NAP_DURATION,
        HealthMetric.SLEEP_LIGHT_DURATION,
        HealthMetric.SLEEP_DEEP_DURATION,
        HealthMetric.SLEEP_REM_DURATION,
        HealthMetric.SLEEP_AWAKE_DURATION,
        HealthMetric.SLEEP_AWAKE_EPISODE_DURATION,
    }

    def load_data(self, user_id: str) -> Sequence[RawHealthRecord]:
        raise NotImplementedError(
            "后端不直接拉取 Health Kit；数据应由获用户授权的 Android 桥接层提交"
        )

    def normalize(
        self, user_id: str, records: Sequence[RawHealthRecord]
    ) -> list[HealthEventCreate]:
        events: list[HealthEventCreate] = []
        for raw in records:
            record = VivoBridgeRecord.model_validate(raw)
            if record.metric not in self._supported_metrics:
                raise ValueError(f"暂不支持 vivo 指标 {record.metric.value}")
            value, unit = self._normalize_unit(
                record.metric, record.value, record.unit
            )
            events.append(
                HealthEventCreate(
                    user_id=user_id,
                    source=HealthSource.VIVO,
                    metric=record.metric,
                    value=value,
                    unit=unit,
                    timestamp=record.measured_at or record.start_time,
                    end_timestamp=record.end_time,
                    source_record_id=record.record_id,
                    provenance=HealthEventProvenance(
                        display_label="vivo 本地健康 Provider",
                        source_system=record.source,
                        source_device=record.source_device,
                        source_status=record.status.value,
                        raw_source=record.raw_source,
                        synced_at=(
                            record.synced_at.isoformat()
                            if record.synced_at is not None
                            else None
                        ),
                    ),
                )
            )
        return events

    @staticmethod
    def _normalize_unit(
        metric: HealthMetric, value: float, raw_unit: str
    ) -> tuple[float, str]:
        unit = raw_unit.strip().lower()
        if metric == HealthMetric.STEPS:
            if unit not in {"step", "steps", "count"}:
                raise ValueError("步数单位只允许 step、steps 或 count")
            if not float(value).is_integer():
                raise ValueError("步数必须是整数")
            return value, "step"
        if metric == HealthMetric.DISTANCE:
            if unit in {"m", "meter", "meters"}:
                return value, "m"
            if unit in {"km", "kilometer", "kilometers"}:
                return value * 1000, "m"
            raise ValueError("距离单位必须是 m 或 km")
        if metric == HealthMetric.CALORIES:
            if unit in {"kcal", "kilocalorie", "kilocalories"}:
                return value, "kcal"
            if unit in {"cal", "calorie", "calories"}:
                return value / 1000, "kcal"
            raise ValueError("卡路里单位必须是 kcal 或 cal")
        if metric in {HealthMetric.HEART_RATE, HealthMetric.HEART_RATE_RESTING}:
            if unit not in {"bpm", "beat/min", "beats/min"}:
                raise ValueError("心率单位必须是 bpm")
            return value, "bpm"
        if metric == HealthMetric.SPO2:
            if unit not in {"%", "percent", "percentage"}:
                raise ValueError("血氧单位必须是 %")
            return value, "%"
        if metric in {
            HealthMetric.STRESS,
            HealthMetric.SLEEP_SCORE,
            HealthMetric.SLEEP_DEEP_CONTINUITY,
        }:
            if unit not in {"score", "point", "points"}:
                raise ValueError("评分指标单位必须是 score")
            return value, "score"
        if metric == HealthMetric.SLEEP_AWAKE_EPISODE_COUNT:
            if unit not in {"count", "times"} or not float(value).is_integer():
                raise ValueError("清醒次数必须是整数 count")
            return value, "count"
        if metric in VivoAdapter._duration_metrics:
            if unit in {"ms", "millisecond", "milliseconds"}:
                return value / 3_600_000, "hour"
            if unit in {"hour", "hours", "h"}:
                return value, "hour"
            if unit in {"minute", "minutes", "min"}:
                return value / 60, "hour"
            if unit in {"second", "seconds", "s"}:
                return value / 3600, "hour"
            raise ValueError("睡眠时长单位必须是 hour、minute 或 second")
        if unit in {"minute", "minutes", "min"}:
            return value, "minute"
        if unit in {"second", "seconds", "s"}:
            return value / 60, "minute"
        raise ValueError("运动时长单位必须是 minute 或 second")
