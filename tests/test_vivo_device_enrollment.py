"""vivo 一次性设备绑定和设备级凭据测试。"""

import base64
from secrets import token_urlsafe

from fastapi.testclient import TestClient
from pydantic import SecretStr
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import get_settings
from app.server_main import app


def encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def device_proof(code: str, device_id: str) -> tuple[str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = encode(
        private_key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    message = (
        "HEALTH_EVENT_DEVICE_ENROLL_V1\n" + code + "\n" + device_id
    ).encode("utf-8")
    proof = encode(private_key.sign(message, ec.ECDSA(hashes.SHA256())))
    return public_key, proof


def test_device_enrollment_is_one_time_and_scopes_sync_credential_to_device() -> None:
    settings = get_settings()
    original_enabled = settings.vivo_sync_enabled
    original_admin_token = settings.vivo_enrollment_admin_token
    original_sync_token = settings.vivo_sync_token
    admin_token = token_urlsafe(32)
    user_id = "enrollment-api-user"
    device_id = "device-enrollment-test-1"
    try:
        settings.vivo_sync_enabled = True
        settings.vivo_enrollment_admin_token = SecretStr(admin_token)
        settings.vivo_sync_token = None
        with TestClient(app) as client:
            profile = {
                "id": user_id,
                "age": 36,
                "gender": "undisclosed",
                "height": 172,
                "weight": 70,
                "goal": "metabolic_health",
            }
            assert client.post("/api/user/profile", json=profile).status_code == 201

            code_response = client.post(
                "/api/integrations/vivo/enrollment-codes",
                json={"user_id": user_id, "expires_in_minutes": 10},
                headers={"Authorization": "Bearer " + admin_token},
            )
            assert code_response.status_code == 201
            enrollment = code_response.json()
            assert enrollment["payload"].startswith("healthevent://pair?")
            public_key, proof = device_proof(enrollment["code"], device_id)

            enroll_response = client.post(
                "/api/integrations/vivo/devices/enroll",
                json={
                    "enrollment_code": enrollment["code"],
                    "device_id": device_id,
                    "public_key": public_key,
                    "proof": proof,
                },
            )
            assert enroll_response.status_code == 200
            device_token = enroll_response.json()["sync_token"]
            assert len(device_token) >= 32

            sync_payload = {
                "user_id": user_id,
                "device_id": device_id,
                "records": [
                    {
                        "record_id": "enrollment-heart-1",
                        "metric": "heart_rate",
                        "value": 68,
                        "unit": "bpm",
                        "start_time": "2026-09-04T07:00:00+08:00",
                        "status": "PASS",
                        "raw_source": "heartRateValue",
                    }
                ],
            }
            sync_response = client.post(
                "/api/integrations/vivo/sync",
                json=sync_payload,
                headers={"Authorization": "Bearer " + device_token},
            )
            assert sync_response.status_code == 200

            replay = client.post(
                "/api/integrations/vivo/devices/enroll",
                json={
                    "enrollment_code": enrollment["code"],
                    "device_id": device_id,
                    "public_key": public_key,
                    "proof": proof,
                },
            )
            assert replay.status_code == 400

            other_device_payload = {**sync_payload, "device_id": "other-device"}
            forbidden = client.post(
                "/api/integrations/vivo/sync",
                json=other_device_payload,
                headers={"Authorization": "Bearer " + device_token},
            )
            assert forbidden.status_code == 403

            revoked = client.delete(
                f"/api/integrations/vivo/devices/{device_id}",
                headers={"Authorization": "Bearer " + admin_token},
            )
            assert revoked.status_code == 204
            assert client.post(
                "/api/integrations/vivo/sync",
                json=sync_payload,
                headers={"Authorization": "Bearer " + device_token},
            ).status_code == 401
    finally:
        settings.vivo_sync_enabled = original_enabled
        settings.vivo_enrollment_admin_token = original_admin_token
        settings.vivo_sync_token = original_sync_token
