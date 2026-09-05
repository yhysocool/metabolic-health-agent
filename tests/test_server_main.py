"""云端最小接收入口不依赖本地 AI 运行时。"""

from fastapi.testclient import TestClient

from app.server_main import app


def test_ingestion_server_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    paths = app.openapi()["paths"]
    assert "/api/integrations/vivo/enrollment-codes" in paths
    assert "/api/integrations/vivo/devices/enroll" in paths
    assert "/api/integrations/vivo/devices/{device_id}" in paths
    assert "/api/integrations/vivo/sync" in paths
    assert "/api/reports/data-quality/{user_id}" in paths
    assert "/api/agent/plan/{user_id}" not in paths
