"""趋势方向算法测试。"""

from datetime import datetime, timedelta, timezone

from app.schemas.health import HealthEvent, HealthMetric, HealthSource, TrendDirection
from app.services.trend_service import TrendService


def make_events(metric: HealthMetric, values: list[float]) -> list[HealthEvent]:
    start = datetime.now(timezone.utc) - timedelta(days=len(values))
    return [
        HealthEvent(
            user_id="test-user",
            source=HealthSource.MOCK,
            metric=metric,
            value=value,
            unit="test-unit",
            timestamp=start + timedelta(days=index),
        )
        for index, value in enumerate(values)
    ]


def test_sleep_increase() -> None:
    events = make_events(HealthMetric.SLEEP, [6.0, 6.1, 7.0, 7.2])
    assert TrendService().analyze_sleep(events) == TrendDirection.INCREASE


def test_weight_decrease() -> None:
    events = make_events(HealthMetric.WEIGHT, [80, 79.8, 76, 75.8])
    assert TrendService().analyze_weight(events) == TrendDirection.DECREASE


def test_insufficient_data_is_stable() -> None:
    events = make_events(HealthMetric.STEPS, [5000, 8000])
    assert TrendService().analyze_activity(events) == TrendDirection.STABLE

