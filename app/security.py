"""生产环境的用户级访问控制。

设备绑定凭据既证明了设备身份，也绑定到一个用户。服务端不再信任
客户端直接提交的 user_id；生产请求必须从设备凭据反推出用户归属。
开发环境继续允许本地演示 API 不带认证运行。
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.dependencies import get_vivo_device_repository
from app.repositories.vivo_devices import VivoDeviceRepository


@dataclass(frozen=True)
class UserPrincipal:
    """当前请求的用户主体。development 模式下 user_id 可以为空。"""

    user_id: str | None
    device_id: str | None = None
    auth_type: str = "development"


async def require_user_access(
    settings: Annotated[Settings, Depends(get_settings)],
    device_repository: Annotated[
        VivoDeviceRepository, Depends(get_vivo_device_repository)
    ],
    authorization: Annotated[str | None, Header()] = None,
) -> UserPrincipal:
    """生产环境只接受绑定设备凭据，开发环境保留本地演示兼容性。"""

    if settings.environment != "production":
        return UserPrincipal(user_id=None)

    scheme, separator, token = (authorization or "").partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户访问凭据无效",
            headers={"WWW-Authenticate": "Bearer"},
        )

    device = await device_repository.get_active_device_by_credential_hash(
        sha256(token.encode("utf-8")).hexdigest()
    )
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户访问凭据无效",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await device_repository.touch_device(device.device_id, datetime.now(timezone.utc))
    return UserPrincipal(
        user_id=device.user_id,
        device_id=device.device_id,
        auth_type="device",
    )


UserAccessDependency = Annotated[
    UserPrincipal, Depends(require_user_access)
]


def ensure_user_scope(principal: UserPrincipal, requested_user_id: str) -> None:
    """确保路径或请求体中的用户归属与凭据一致。"""

    if principal.user_id is not None and not compare_digest(
        principal.user_id, requested_user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问其他用户的数据",
        )
