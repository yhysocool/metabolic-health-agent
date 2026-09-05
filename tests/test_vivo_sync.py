"""vivo 增量同步、幂等写入和接口保护测试。"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import get_settings
from app.main import app
from app.repositories.memory import InMemoryHealthRepository
from app.schemas.integration import VivoBridgeRecord, VivoSyncRequest
from app.schemas.user import HealthGoal, UserProfileCreate
from app.services.vivo_sync_service import VivoSyncService


async def test_vivo_sync_is_idempotent_and_updates_changed_record() -> None:
    repository = InMemoryHealthRepository()
    user_id = "vivo-service-user"
    await repository.save_user(
        UserProfileCreate(
            id=user_id,
            age=36,
            height=172,
            weight=70,
            goal=HealthGoal.METABOLIC_HEALTH,
        )
    )
    service = VivoSyncService(repository)
    timestamp = datetime(2026, 8, 24, 7, tzinfo=timezone.utc)

    def request(value: float, cursor: str) -> VivoSyncRequest:
        return VivoSyncRequest(
            batch_id="batch-" + cursor,
            user_id=user_id,
            device_id="raw-device-id-must-not-be-stored",
            cursor=cursor,
            records=[
                VivoBridgeRecord(
                    record_id="steps-1",
                    metric="steps",
                    value=value,
                    unit="count",
                    source="vivo_assistant_step_provider",
                    source_device="vivo_health_provider",
                    measured_at=timestamp,
                    start_time=timestamp,
                    raw_source="step",
                    synced_at=timestamp,
                )
            ],
        )

    first = await service.sync(request(8000, "cursor-1"))
    replay = await service.sync(request(8000, "cursor-1"))
    changed = await service.sync(request(8200, "cursor-2"))

    assert (first.created, first.updated, first.unchanged) == (1, 0, 0)
    assert first.batch_id == "batch-cursor-1"
    assert (replay.created, replay.updated, replay.unchanged) == (0, 0, 1)
    assert (changed.created, changed.updated, changed.unchanged) == (0, 1, 0)
    events = await repository.get_events(user_id)
    assert len(events) == 1
    assert events[0].value == 8200
    assert events[0].provenance is not None
    assert events[0].provenance.source_system == "vivo_assistant_step_provider"
    assert events[0].provenance.source_device == "vivo_health_provider"
    state = await repository.get_integration_state(user_id, changed.provider)
    assert state is not None
    assert state.cursor == "cursor-2"
    assert state.device_id_hash != "raw-device-id-must-not-be-stored"
    assert len(state.device_id_hash) == 64


async def test_vivo_sync_accepts_spo2_and_sleep_detail_metrics() -> None:
    repository = InMemoryHealthRepository()
    user_id = "vivo-expanded-metrics-user"
    await repository.save_user(
        UserProfileCreate(
            id=user_id,
            age=36,
            height=172,
            weight=70,
            goal=HealthGoal.METABOLIC_HEALTH,
        )
    )
    timestamp = datetime(2026, 9, 4, 0, 34, tzinfo=timezone.utc)
    request = VivoSyncRequest(
        batch_id="expanded-metrics-batch",
        user_id=user_id,
        device_id="fixture-device",
        records=[
            VivoBridgeRecord(
                record_id="spo2-1",
                metric="spo2",
                value=94,
                unit="%",
                source_device="vivo_health_provider",
                measured_at=timestamp,
                start_time=timestamp,
                raw_source="saO2Value",
                synced_at=timestamp,
            ),
            VivoBridgeRecord(
                record_id="sleep-total-1",
                metric="sleep_total_duration",
                value=10_800_000,
                unit="ms",
                source_device="vivo_health_provider",
                measured_at=timestamp,
                start_time=timestamp,
                raw_source="totalDuration",
                synced_at=timestamp,
            ),
        ],
    )

    result = await VivoSyncService(repository).sync(request)
    events = await repository.get_events(user_id)

    assert result.created == 2
    assert {(item.metric.value, item.value, item.unit) for item in events} == {
        ("spo2", 94, "%"),
        ("sleep_total_duration", 3, "hour"),
    }


def test_vivo_sync_api_is_disabled_by_default_and_supports_fixture_sync() -> None:
    settings = get_settings()
    original_enabled = settings.vivo_sync_enabled
    original_token = settings.vivo_sync_token
    user_id = "vivo-api-user"
    payload = {
        "batch_id": "fixture-batch-1",
        "user_id": user_id,
        "device_id": "fixture-device",
        "cursor": "fixture-cursor-1",
        "records": [
            {
                "record_id": "heart-1",
                "metric": "heart_rate",
                "value": 68,
                "unit": "bpm",
                "source": "vivo_private_health_provider",
                "source_device": "vivo_health_provider",
                "measured_at": "2026-08-24T07:00:00+08:00",
                "start_time": "2026-08-24T07:00:00+08:00",
                "end_time": None,
                "status": "PASS",
                "raw_source": "heartRateValue",
                "synced_at": "2026-08-24T07:01:00+08:00",
            }
        ],
    }
    try:
        settings.vivo_sync_enabled = False
        with TestClient(app) as client:
            assert client.post("/api/integrations/vivo/sync", json=payload).status_code == 503

            profile = {
                "id": user_id,
                "age": 36,
                "gender": "undisclosed",
                "height": 172,
                "weight": 70,
                "goal": "metabolic_health",
            }
            assert client.post("/api/user/profile", json=profile).status_code == 201
            settings.vivo_sync_enabled = True
            settings.vivo_sync_token = SecretStr("fixture-only-token-32-characters!!")
            assert client.post("/api/integrations/vivo/sync", json=payload).status_code == 401

            headers = {
                "Authorization": "Bearer fixture-only-token-32-characters!!"
            }
            response = client.post(
                "/api/integrations/vivo/sync", json=payload, headers=headers
            )
            assert response.status_code == 200
            assert response.json()["batch_id"] == "fixture-batch-1"
            assert response.json()["created"] == 1
            status_response = client.get(
                f"/api/integrations/vivo/status/{user_id}", headers=headers
            )
            assert status_response.status_code == 200
            assert status_response.json()["connected"] is True
            assert "device_id" not in status_response.json()
    finally:
        settings.vivo_sync_enabled = original_enabled
        settings.vivo_sync_token = original_token
