"""vivo 设备一次性绑定和设备凭据仓储。"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import VivoDeviceCredentialModel, VivoEnrollmentCodeModel


@dataclass(frozen=True)
class VivoEnrollmentCode:
    id: str
    user_id: str
    code_hash: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None


@dataclass(frozen=True)
class VivoDeviceCredential:
    device_id: str
    user_id: str
    public_key: str
    credential_hash: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class VivoDeviceRepository(Protocol):
    async def create_enrollment(
        self,
        user_id: str,
        code_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> VivoEnrollmentCode: ...

    async def register_device(
        self,
        code_hash: str,
        device_id: str,
        public_key: str,
        credential_hash: str,
        now: datetime,
    ) -> VivoDeviceCredential: ...

    async def get_active_device_by_credential_hash(
        self, credential_hash: str
    ) -> VivoDeviceCredential | None: ...

    async def touch_device(self, device_id: str, used_at: datetime) -> None: ...

    async def revoke_device(self, device_id: str, revoked_at: datetime) -> bool: ...


class InMemoryVivoDeviceRepository(VivoDeviceRepository):
    """测试和本地开发使用的设备绑定仓储。"""

    def __init__(self) -> None:
        self._codes: dict[str, VivoEnrollmentCode] = {}
        self._devices: dict[str, VivoDeviceCredential] = {}
        self._lock = asyncio.Lock()

    async def create_enrollment(
        self,
        user_id: str,
        code_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> VivoEnrollmentCode:
        enrollment = VivoEnrollmentCode(
            id=str(uuid4()),
            user_id=user_id,
            code_hash=code_hash,
            created_at=created_at,
            expires_at=expires_at,
            used_at=None,
        )
        async with self._lock:
            self._codes[code_hash] = enrollment
        return enrollment

    async def register_device(
        self,
        code_hash: str,
        device_id: str,
        public_key: str,
        credential_hash: str,
        now: datetime,
    ) -> VivoDeviceCredential:
        async with self._lock:
            enrollment = self._codes.get(code_hash)
            if enrollment is None:
                raise LookupError("绑定码无效")
            if enrollment.used_at is not None:
                raise ValueError("绑定码已经使用")
            if enrollment.expires_at <= now:
                raise ValueError("绑定码已经过期")

            existing = self._devices.get(device_id)
            if existing is not None and existing.user_id != enrollment.user_id:
                raise ValueError("设备已经绑定到其他用户")

            created_at = existing.created_at if existing is not None else now
            device = VivoDeviceCredential(
                device_id=device_id,
                user_id=enrollment.user_id,
                public_key=public_key,
                credential_hash=credential_hash,
                created_at=created_at,
                last_used_at=None,
                revoked_at=None,
            )
            self._devices[device_id] = device
            self._codes[code_hash] = VivoEnrollmentCode(
                id=enrollment.id,
                user_id=enrollment.user_id,
                code_hash=enrollment.code_hash,
                created_at=enrollment.created_at,
                expires_at=enrollment.expires_at,
                used_at=now,
            )
            return device

    async def get_active_device_by_credential_hash(
        self, credential_hash: str
    ) -> VivoDeviceCredential | None:
        async with self._lock:
            return next(
                (
                    item
                    for item in self._devices.values()
                    if item.credential_hash == credential_hash and item.revoked_at is None
                ),
                None,
            )

    async def touch_device(self, device_id: str, used_at: datetime) -> None:
        async with self._lock:
            device = self._devices.get(device_id)
            if device is not None:
                self._devices[device_id] = VivoDeviceCredential(
                    device_id=device.device_id,
                    user_id=device.user_id,
                    public_key=device.public_key,
                    credential_hash=device.credential_hash,
                    created_at=device.created_at,
                    last_used_at=used_at,
                    revoked_at=device.revoked_at,
                )

    async def revoke_device(self, device_id: str, revoked_at: datetime) -> bool:
        async with self._lock:
            device = self._devices.get(device_id)
            if device is None or device.revoked_at is not None:
                return False
            self._devices[device_id] = VivoDeviceCredential(
                device_id=device.device_id,
                user_id=device.user_id,
                public_key=device.public_key,
                credential_hash=device.credential_hash,
                created_at=device.created_at,
                last_used_at=device.last_used_at,
                revoked_at=revoked_at,
            )
            return True

    async def clear(self) -> None:
        async with self._lock:
            self._codes.clear()
            self._devices.clear()


class SQLAlchemyVivoDeviceRepository(VivoDeviceRepository):
    """PostgreSQL 设备绑定仓储；消费绑定码与注册设备在一个事务中完成。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_enrollment(
        self,
        user_id: str,
        code_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> VivoEnrollmentCode:
        model = VivoEnrollmentCodeModel(
            id=str(uuid4()),
            user_id=user_id,
            code_hash=code_hash,
            created_at=created_at,
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.commit()
        return VivoEnrollmentCode(
            id=model.id,
            user_id=model.user_id,
            code_hash=model.code_hash,
            created_at=model.created_at,
            expires_at=model.expires_at,
            used_at=model.used_at,
        )

    async def register_device(
        self,
        code_hash: str,
        device_id: str,
        public_key: str,
        credential_hash: str,
        now: datetime,
    ) -> VivoDeviceCredential:
        try:
            async with self._session.begin():
                enrollment = await self._session.scalar(
                    select(VivoEnrollmentCodeModel)
                    .where(VivoEnrollmentCodeModel.code_hash == code_hash)
                    .with_for_update()
                )
                if enrollment is None:
                    raise LookupError("绑定码无效")
                if enrollment.used_at is not None:
                    raise ValueError("绑定码已经使用")
                if enrollment.expires_at <= now:
                    raise ValueError("绑定码已经过期")

                device = await self._session.get(
                    VivoDeviceCredentialModel, device_id, with_for_update=True
                )
                if device is not None and device.user_id != enrollment.user_id:
                    raise ValueError("设备已经绑定到其他用户")
                if device is None:
                    device = VivoDeviceCredentialModel(
                        device_id=device_id,
                        user_id=enrollment.user_id,
                        public_key=public_key,
                        credential_hash=credential_hash,
                        created_at=now,
                    )
                    self._session.add(device)
                else:
                    device.user_id = enrollment.user_id
                    device.public_key = public_key
                    device.credential_hash = credential_hash
                    device.revoked_at = None
                    device.last_used_at = None
                enrollment.used_at = now

            return VivoDeviceCredential(
                device_id=device.device_id,
                user_id=device.user_id,
                public_key=device.public_key,
                credential_hash=device.credential_hash,
                created_at=device.created_at,
                last_used_at=device.last_used_at,
                revoked_at=device.revoked_at,
            )
        except Exception:
            await self._session.rollback()
            raise

    async def get_active_device_by_credential_hash(
        self, credential_hash: str
    ) -> VivoDeviceCredential | None:
        model = await self._session.scalar(
            select(VivoDeviceCredentialModel).where(
                VivoDeviceCredentialModel.credential_hash == credential_hash,
                VivoDeviceCredentialModel.revoked_at.is_(None),
            )
        )
        if model is None:
            return None
        return VivoDeviceCredential(
            device_id=model.device_id,
            user_id=model.user_id,
            public_key=model.public_key,
            credential_hash=model.credential_hash,
            created_at=model.created_at,
            last_used_at=model.last_used_at,
            revoked_at=model.revoked_at,
        )

    async def touch_device(self, device_id: str, used_at: datetime) -> None:
        model = await self._session.get(VivoDeviceCredentialModel, device_id)
        if model is None or model.revoked_at is not None:
            return
        model.last_used_at = used_at
        await self._session.commit()

    async def revoke_device(self, device_id: str, revoked_at: datetime) -> bool:
        model = await self._session.get(VivoDeviceCredentialModel, device_id)
        if model is None or model.revoked_at is not None:
            return False
        model.revoked_at = revoked_at
        await self._session.commit()
        return True
