"""生产环境用户级认证和授权测试。"""

from datetime import datetime, timezone
from hashlib import sha256

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.config import Settings
from app.repositories.vivo_devices import InMemoryVivoDeviceRepository
from app.security import ensure_user_scope, require_user_access


@pytest.mark.asyncio
async def test_production_access_resolves_user_from_active_device_credential() -> None:
    repository = InMemoryVivoDeviceRepository()
    code = "one-time-enrollment-code-123456"
    token = "device-sync-token-12345678901234567890"
    now = datetime.now(timezone.utc)
    await repository.create_enrollment(
        "owner-user", sha256(code.encode()).hexdigest(), now, now.replace(year=now.year + 1)
    )
    await repository.register_device(
        sha256(code.encode()).hexdigest(),
        "owner-device",
        "public-key",
        sha256(token.encode()).hexdigest(),
        now,
    )

    principal = await require_user_access(
        Settings(environment="production"),
        repository,
        "Bearer " + token,
    )

    assert principal.user_id == "owner-user"
    assert principal.device_id == "owner-device"
    ensure_user_scope(principal, "owner-user")
    with pytest.raises(HTTPException) as error:
        ensure_user_scope(principal, "other-user")
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_production_access_rejects_global_sync_token_and_missing_token() -> None:
    repository = InMemoryVivoDeviceRepository()
    settings = Settings(
        environment="production",
        vivo_sync_token=SecretStr("legacy-global-token-should-not-authorize-user-api"),
    )
    for authorization in (None, "Bearer legacy-global-token-should-not-authorize-user-api"):
        with pytest.raises(HTTPException) as error:
            await require_user_access(settings, repository, authorization)
        assert error.value.status_code == 401
