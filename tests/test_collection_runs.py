"""采集运行诊断和确定性质量报告测试。"""

from datetime import datetime, timezone

import pytest

from app.repositories.collection_runs import InMemoryCollectionRunRepository
from app.repositories.memory import InMemoryHealthRepository
from app.schemas.health import HealthEventCreate, HealthMetric, HealthSource
from app.schemas.integration import (
    VivoBridgeRecord,
    VivoCollectionRun,
    VivoSyncRequest,
)
from app.schemas.user import HealthGoal, UserProfileCreate
from app.services.data_quality import DataQualityReportService
from app.services.vivo_sync_service import VivoSyncService


@pytest.mark.asyncio
async def test_sync_accepts_diagnostic_only_batch_and_quality_report_aggregates_it() -> None:
    health_repository = InMemoryHealthRepository()
    collection_repository = InMemoryCollectionRunRepository()
    user_id = "quality-report-user"
    await health_repository.save_user(
        UserProfileCreate(
            id=user_id,
            age=36,
            height=172,
            weight=70,
            goal=HealthGoal.METABOLIC_HEALTH,
        )
    )
    measured_at = datetime(2026, 9, 4, 8, tzinfo=timezone.utc)
    run = VivoCollectionRun(
        run_id="vivo-snapshot-1",
        read_at=measured_at,
        status="PASS",
        provider_row_count=4,
        valid_record_count=2,
        first_measured_at=measured_at,
        last_measured_at=measured_at,
    )
    request = VivoSyncRequest(
        user_id=user_id,
        device_id="quality-device",
        cursor="cursor-1",
        collection_runs=[run],
        records=[],
    )

    result = await VivoSyncService(health_repository).sync(
        request, collection_repository
    )

    assert result.received == 0
    assert result.collection_runs_received == 1
    assert result.collection_runs_created == 1
    assert await collection_repository.list_runs(user_id)

    await health_repository.add_event(
        HealthEventCreate(
            user_id=user_id,
            source=HealthSource.VIVO,
            metric=HealthMetric.HEART_RATE,
            value=68,
            unit="bpm",
            timestamp=measured_at,
        )
    )
    report = await DataQualityReportService(
        health_repository, collection_repository
    ).build(user_id, 30)

    assert report.event_count == 1
    assert report.collection_run_count == 1
    assert report.provider_rows == 4
    assert report.valid_records == 2
    assert report.metrics[0].metric == "heart_rate"


def test_sync_request_rejects_empty_batch_without_diagnostics() -> None:
    with pytest.raises(ValueError):
        VivoSyncRequest(user_id="user", device_id="device", records=[])


def test_collection_run_allows_multiple_metrics_from_one_provider_row() -> None:
    run = VivoCollectionRun(
        run_id="vivo-snapshot-multi-metric",
        read_at=datetime(2026, 9, 5, 8, tzinfo=timezone.utc),
        status="PASS",
        provider_row_count=1,
        valid_record_count=17,
    )

    assert run.provider_row_count == 1
    assert run.valid_record_count == 17
