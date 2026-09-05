"""Adapter 统一输出契约测试。"""

from datetime import datetime, timezone

import pytest

from app.adapters.mock_adapter import MockHealthAdapter
from app.adapters.synthetic_adapter import SyntheticHealthAdapter
from app.adapters.vivo_adapter import VivoAdapter
from app.schemas.health import HealthMetric, HealthSource


def test_mock_adapter_generates_30_days_of_four_metrics() -> None:
    events = MockHealthAdapter(days=30, seed=7).collect("mock-user")
    assert len(events) == 120
    assert {event.metric for event in events} == {
        HealthMetric.SLEEP,
        HealthMetric.STEPS,
        HealthMetric.HEART_RATE,
        HealthMetric.EXERCISE,
    }
    assert all(event.source == HealthSource.MOCK for event in events)
    assert all(event.user_id == "mock-user" for event in events)


def test_mock_adapter_is_repeatable_for_same_seed() -> None:
    first = MockHealthAdapter(days=2, seed=8).collect("mock-user")
    second = MockHealthAdapter(days=2, seed=8).collect("mock-user")
    assert [event.value for event in first] == [event.value for event in second]


def test_synthetic_adapter_marks_every_event_and_separates_reference_scope() -> None:
    events = SyntheticHealthAdapter(days=30, seed=7).collect("demo-user")

    assert len(events) == 120
    assert all(event.source == HealthSource.SYNTHETIC for event in events)
    assert all(event.source_record_id for event in events)
    assert all(event.provenance and event.provenance.is_synthetic for event in events)
    referenced = {
        event.metric
        for event in events
        if event.provenance and event.provenance.reference_dataset == "NHANES"
    }
    assert referenced == {HealthMetric.SLEEP, HealthMetric.EXERCISE}
    assert all(
        event.provenance and event.provenance.reference_dataset is None
        for event in events
        if event.metric in {HealthMetric.STEPS, HealthMetric.HEART_RATE}
    )


def test_synthetic_adapter_is_repeatable_for_same_seed() -> None:
    first = SyntheticHealthAdapter(days=2, seed=8).collect("demo-user")
    second = SyntheticHealthAdapter(days=2, seed=8).collect("demo-user")
    assert [event.value for event in first] == [event.value for event in second]


def test_vivo_adapter_normalizes_bridge_units_and_source_ids() -> None:
    timestamp = datetime(2026, 8, 24, 7, tzinfo=timezone.utc)
    events = VivoAdapter().normalize(
        "vivo-user",
        [
            {
                "record_id": "sleep-1",
                "metric": "sleep",
                "value": 450,
                "unit": "minute",
                "start_time": timestamp,
            },
            {
                "record_id": "steps-1",
                "metric": "steps",
                "value": 8200,
                "unit": "count",
                "start_time": timestamp,
            },
        ],
    )

    assert events[0].value == 7.5
    assert events[0].unit == "hour"
    assert events[0].source_record_id == "sleep-1"
    assert events[1].unit == "step"
    assert all(event.source == HealthSource.VIVO for event in events)


def test_vivo_adapter_rejects_unsupported_health_metric() -> None:
    with pytest.raises(ValueError, match="暂不支持 vivo 指标 blood_glucose"):
        VivoAdapter().normalize(
            "vivo-user",
            [
                {
                    "record_id": "glucose-1",
                    "metric": "blood_glucose",
                    "value": 5.2,
                    "unit": "mmol/L",
                    "start_time": "2026-08-24T07:00:00+08:00",
                }
            ],
        )
