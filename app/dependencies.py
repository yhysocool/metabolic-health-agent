"""FastAPI 依赖装配入口，集中决定使用 Mock 或 PostgreSQL 仓储。"""

from collections.abc import AsyncIterator

from app.config import get_settings
from app.database.database import AsyncSessionFactory
from app.repositories.base import HealthRepository
from app.repositories.collection_runs import (
    CollectionRunRepository,
    InMemoryCollectionRunRepository,
    SQLAlchemyCollectionRunRepository,
)
from app.repositories.memory import InMemoryHealthRepository
from app.repositories.nhanes_reference import NHANESReferenceRepository
from app.repositories.sqlalchemy import SQLAlchemyHealthRepository
from app.repositories.vivo_devices import (
    InMemoryVivoDeviceRepository,
    SQLAlchemyVivoDeviceRepository,
    VivoDeviceRepository,
)


_memory_repository = InMemoryHealthRepository()
_nhanes_reference_repository = NHANESReferenceRepository()
_vivo_device_repository = InMemoryVivoDeviceRepository()
_collection_run_repository = InMemoryCollectionRunRepository()


def get_memory_repository() -> InMemoryHealthRepository:
    """返回默认 Mock 仓储，供启动数据和测试复用。"""

    return _memory_repository


def get_nhanes_reference_repository() -> NHANESReferenceRepository:
    """返回只读 NHANES 聚合参照仓储。"""

    return _nhanes_reference_repository


async def get_health_repository() -> AsyncIterator[HealthRepository]:
    """按配置为每个请求提供仓储实例。"""

    if get_settings().repository_backend == "memory":
        yield _memory_repository
        return

    async with AsyncSessionFactory() as session:
        yield SQLAlchemyHealthRepository(session)


async def get_vivo_device_repository() -> AsyncIterator[VivoDeviceRepository]:
    """按配置提供持久化或内存设备绑定仓储。"""

    if get_settings().repository_backend == "memory":
        yield _vivo_device_repository
        return

    async with AsyncSessionFactory() as session:
        yield SQLAlchemyVivoDeviceRepository(session)


async def get_collection_run_repository() -> AsyncIterator[CollectionRunRepository]:
    """按配置提供采集运行摘要仓储。"""

    if get_settings().repository_backend == "memory":
        yield _collection_run_repository
        return

    async with AsyncSessionFactory() as session:
        yield SQLAlchemyCollectionRunRepository(session)
