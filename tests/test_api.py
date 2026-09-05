"""FastAPI 默认本地合成演示模式的基础契约测试。"""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_health_check_and_synthetic_demo_status() -> None:
    with TestClient(app) as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["data_mode"] == "synthetic_demo"

        user_id = get_settings().demo_user_id
        status = client.get(f"/api/health/status/{user_id}")
        assert status.status_code == 200
        assert status.json()["user_id"] == user_id
        assert "本地合成演示数据" in status.json()["data_notice"]
        assert status.json()["disclaimer"]

        events = client.get(f"/api/health/events/{user_id}?days=30")
        assert events.status_code == 200
        payload = events.json()
        assert payload["user_id"] == user_id
        assert payload["window_days"] == 30
        assert payload["count"] == 120
        assert len(payload["items"]) == 120
        timestamps = [item["timestamp"] for item in payload["items"]]
        assert timestamps == sorted(timestamps)
        assert {item["source"] for item in payload["items"]} == {"synthetic"}
        assert all(item["provenance"]["is_synthetic"] for item in payload["items"])
        referenced_metrics = {
            item["metric"]
            for item in payload["items"]
            if item["provenance"]["reference_dataset"] == "NHANES"
        }
        assert referenced_metrics == {"sleep", "exercise"}


def test_missing_user_returns_404() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health/status/not-found")
        assert response.status_code == 404

        events = client.get("/api/health/events/not-found")
        assert events.status_code == 404


def test_health_event_window_is_validated() -> None:
    with TestClient(app) as client:
        user_id = get_settings().demo_user_id
        assert client.get(f"/api/health/events/{user_id}?days=0").status_code == 422
        assert client.get(f"/api/health/events/{user_id}?days=366").status_code == 422
