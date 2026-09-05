"""过去一段时间内的基础趋势分析。"""

from collections.abc import Sequence
from statistics import fmean

from app.schemas.health import HealthEvent, HealthMetric, TrendDirection


class TrendService:
    """通过前后半段均值变化识别方向，避免对日波动过度反应。"""

    def __init__(self, change_threshold: float = 0.03) -> None:
        self.change_threshold = change_threshold

    def _analyze_values(self, values: Sequence[float]) -> TrendDirection:
        if len(values) < 4:
            return TrendDirection.STABLE
        midpoint = len(values) // 2
        earlier = fmean(values[:midpoint])
        later = fmean(values[midpoint:])
        if abs(earlier) < 1e-9:
            return TrendDirection.STABLE
        ratio = (later - earlier) / abs(earlier)
        if ratio > self.change_threshold:
            return TrendDirection.INCREASE
        if ratio < -self.change_threshold:
            return TrendDirection.DECREASE
        return TrendDirection.STABLE

    @staticmethod
    def _values(events: Sequence[HealthEvent], metric: HealthMetric) -> list[float]:
        return [
            event.value
            for event in sorted(events, key=lambda item: item.timestamp)
            if event.metric == metric
        ]

    def analyze_sleep(self, events: Sequence[HealthEvent]) -> TrendDirection:
        """分析睡眠时长趋势。"""

        return self._analyze_values(self._values(events, HealthMetric.SLEEP))

    def analyze_activity(self, events: Sequence[HealthEvent]) -> TrendDirection:
        """优先使用步数分析活动趋势。"""

        values = self._values(events, HealthMetric.STEPS)
        if not values:
            values = self._values(events, HealthMetric.EXERCISE)
        return self._analyze_values(values)

    def analyze_weight(self, events: Sequence[HealthEvent]) -> TrendDirection:
        """分析体重趋势。"""

        return self._analyze_values(self._values(events, HealthMetric.WEIGHT))

