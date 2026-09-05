"""外部健康数据集成 API。"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from hmac import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.dependencies import (
    get_collection_run_repository,
    get_health_repository,
    get_vivo_device_repository,
)
from app.repositories.base import HealthRepository
from app.repositories.collection_runs import CollectionRunRepository
from app.repositories.vivo_devices import VivoDeviceRepository
from app.schemas.integration import (
    VivoDeviceEnrollmentRequest,
    VivoDeviceEnrollmentResponse,
    VivoEnrollmentCodeRequest,
    VivoEnrollmentCodeResponse,
    VivoSyncRequest,
    VivoSyncResult,
    VivoSyncStatus,
)
from app.services.vivo_device_enrollment import VivoDeviceEnrollmentService
from app.services.vivo_sync_service import VivoSyncService


router = APIRouter(prefix="/integrations", tags=["integrations"])
RepositoryDependency = Annotated[HealthRepository, Depends(get_health_repository)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
DeviceRepositoryDependency = Annotated[
    VivoDeviceRepository, Depends(get_vivo_device_repository)
]
CollectionRunDependency = Annotated[
    CollectionRunRepository, Depends(get_collection_run_repository)
]


@dataclass(frozen=True)
class VivoAccessContext:
    """同步调用的身份；global 仅兼容旧版，device 才是新 App 身份。"""

    kind: str
    user_id: str | None = None
    device_id: str | None = None


async def require_vivo_sync_access(
    settings: SettingsDependency,
    device_repository: DeviceRepositoryDependency,
    authorization: Annotated[str | None, Header()] = None,
) -> VivoAccessContext:
    """接受旧版全局令牌或已绑定设备令牌，优先使用设备级凭据。"""

    if not settings.vivo_sync_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="vivo 同步入口尚未启用",
        )
    scheme, separator, token = (authorization or "").partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="vivo 同步凭据无效",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.vivo_sync_token is not None:
        expected = settings.vivo_sync_token.get_secret_value()
        if len(expected) >= 32 and compare_digest(token, expected):
            return VivoAccessContext(kind="global")

    device = await device_repository.get_active_device_by_credential_hash(
        sha256(token.encode("utf-8")).hexdigest()
    )
    if device is not None:
        await device_repository.touch_device(device.device_id, datetime.now(timezone.utc))
        return VivoAccessContext(
            kind="device", user_id=device.user_id, device_id=device.device_id
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="vivo 同步凭据无效",
        headers={"WWW-Authenticate": "Bearer"},
    )


VivoAccessDependency = Annotated[VivoAccessContext, Depends(require_vivo_sync_access)]


def require_vivo_enrollment_admin_access(
    settings: SettingsDependency,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """绑定码生成只允许服务器管理员调用，不下发管理员令牌到 App。"""

    configured = settings.vivo_enrollment_admin_token
    if configured is None or len(configured.get_secret_value()) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="设备绑定管理员凭据尚未配置",
        )
    scheme, separator, token = (authorization or "").partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not compare_digest(
        token, configured.get_secret_value()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="设备绑定管理员凭据无效",
            headers={"WWW-Authenticate": "Bearer"},
        )


VivoEnrollmentAdminDependency = Annotated[
    None, Depends(require_vivo_enrollment_admin_access)
]


@router.post(
    "/vivo/enrollment-codes",
    response_model=VivoEnrollmentCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_vivo_enrollment_code(
    request: VivoEnrollmentCodeRequest,
    repository: RepositoryDependency,
    device_repository: DeviceRepositoryDependency,
    _: VivoEnrollmentAdminDependency,
) -> VivoEnrollmentCodeResponse:
    """管理员生成一次性载荷，再将 payload 转成二维码展示给用户。"""

    try:
        return await VivoDeviceEnrollmentService(device_repository).create_code(
            request.user_id, request.expires_in_minutes, repository
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/vivo/devices/enroll",
    response_model=VivoDeviceEnrollmentResponse,
)
async def enroll_vivo_device(
    request: VivoDeviceEnrollmentRequest,
    settings: SettingsDependency,
    device_repository: DeviceRepositoryDependency,
) -> VivoDeviceEnrollmentResponse:
    """设备使用一次性绑定码注册公钥并获取设备级同步凭据。"""

    if not settings.vivo_sync_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="vivo 同步入口尚未启用",
        )
    try:
        return await VivoDeviceEnrollmentService(device_repository).enroll(request)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/vivo/devices/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_vivo_device(
    device_id: str,
    device_repository: DeviceRepositoryDependency,
    _: VivoEnrollmentAdminDependency,
) -> None:
    """管理员撤销单台设备，不影响同一用户的其他设备。"""

    if not await device_repository.revoke_device(device_id, datetime.now(timezone.utc)):
        raise HTTPException(status_code=404, detail="设备不存在或已经撤销")


@router.post("/vivo/sync", response_model=VivoSyncResult)
async def sync_vivo_records(
    request: VivoSyncRequest,
    repository: RepositoryDependency,
    collection_repository: CollectionRunDependency,
    access: VivoAccessDependency,
) -> VivoSyncResult:
    """接收 Android 桥接层已经获授权并转换后的增量记录。"""

    if access.kind == "device" and (
        access.user_id != request.user_id or access.device_id != request.device_id
    ):
        raise HTTPException(status_code=403, detail="设备凭据与上传数据归属不匹配")
    try:
        return await VivoSyncService(repository).sync(
            request, collection_repository
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/vivo/status/{user_id}", response_model=VivoSyncStatus)
async def get_vivo_sync_status(
    user_id: str,
    repository: RepositoryDependency,
    access: VivoAccessDependency,
) -> VivoSyncStatus:
    """返回不含设备原始标识的最近同步状态。"""

    if access.kind == "device" and access.user_id != user_id:
        raise HTTPException(status_code=403, detail="设备凭据不能查询其他用户状态")
    try:
        return await VivoSyncService(repository).get_status(user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
