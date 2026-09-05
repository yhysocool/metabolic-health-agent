"""vivo 一次性设备绑定与设备级凭据签发。"""

from base64 import urlsafe_b64decode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from urllib.parse import urlencode

from app.repositories.base import HealthRepository
from app.repositories.vivo_devices import VivoDeviceRepository
from app.schemas.integration import (
    VivoDeviceEnrollmentRequest,
    VivoDeviceEnrollmentResponse,
    VivoEnrollmentCodeResponse,
)


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return urlsafe_b64decode(value + padding)


def enrollment_proof_message(enrollment_code: str, device_id: str) -> bytes:
    return (
        "HEALTH_EVENT_DEVICE_ENROLL_V1\n"
        + enrollment_code.strip()
        + "\n"
        + device_id.strip()
    ).encode("utf-8")


def verify_enrollment_proof(
    public_key: str, proof: str, enrollment_code: str, device_id: str
) -> None:
    """验证 Android Keystore 私钥对绑定码的签名。"""

    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        key = serialization.load_der_public_key(_decode_base64url(public_key))
        if not isinstance(key, ec.EllipticCurvePublicKey) or key.curve.name != "secp256r1":
            raise ValueError("设备公钥算法不受支持")
        key.verify(
            _decode_base64url(proof),
            enrollment_proof_message(enrollment_code, device_id),
            ec.ECDSA(hashes.SHA256()),
        )
    except ImportError as exc:
        raise RuntimeError("服务器缺少设备绑定密码学依赖 cryptography") from exc
    except Exception as exc:
        raise ValueError("设备绑定证明无效") from exc


class VivoDeviceEnrollmentService:
    """不把全局服务器令牌下发给 App，改为一次性绑定后签发设备级凭据。"""

    def __init__(self, device_repository: VivoDeviceRepository) -> None:
        self._devices = device_repository

    async def create_code(
        self,
        user_id: str,
        expires_in_minutes: int,
        health_repository: HealthRepository,
    ) -> VivoEnrollmentCodeResponse:
        if await health_repository.get_user(user_id) is None:
            raise LookupError(f"用户 {user_id} 不存在")
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=expires_in_minutes)
        code = secrets.token_urlsafe(32)
        await self._devices.create_enrollment(
            user_id=user_id,
            code_hash=sha256(code.encode("utf-8")).hexdigest(),
            created_at=now,
            expires_at=expires_at,
        )
        payload = "healthevent://pair?" + urlencode({"code": code, "user_id": user_id})
        return VivoEnrollmentCodeResponse(
            user_id=user_id,
            code=code,
            payload=payload,
            expires_at=expires_at,
        )

    async def enroll(
        self, request: VivoDeviceEnrollmentRequest
    ) -> VivoDeviceEnrollmentResponse:
        code = request.enrollment_code.strip()
        device_id = request.device_id.strip()
        verify_enrollment_proof(request.public_key, request.proof, code, device_id)
        sync_token = secrets.token_urlsafe(48)
        device = await self._devices.register_device(
            code_hash=sha256(code.encode("utf-8")).hexdigest(),
            device_id=device_id,
            public_key=request.public_key,
            credential_hash=sha256(sync_token.encode("utf-8")).hexdigest(),
            now=datetime.now(timezone.utc),
        )
        return VivoDeviceEnrollmentResponse(
            device_id=device.device_id,
            user_id=device.user_id,
            sync_token=sync_token,
        )
