"""Provider 采集运行摘要的仓储。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import VivoCollectionRunModel
from app.schemas.integration import VivoCollectionRun


class CollectionRunRepository(Protocol):
    async def save_runs(
        self,
        runs: list[VivoCollectionRun],
        user_id: str,
        device_id_hash: str,
    ) -> int: ...

    async def list_runs(
        self,
        user_id: str,
        since: datetime | None = None,
    ) -> list[VivoCollectionRun]: ...


@dataclass(frozen=True)
class _StoredRun:
    user_id: str
    device_id_hash: str
    run: VivoCollectionRun


class InMemoryCollectionRunRepository(CollectionRunRepository):
    """测试和本地演示使用的内存仓储。"""

    def __init__(self) -> None:
        self._runs: dict[str, _StoredRun] = {}

    async def save_runs(
        self,
        runs: list[VivoCollectionRun],
        user_id: str,
        device_id_hash: str,
    ) -> int:
        created = 0
        for run in runs:
            existing = self._runs.get(run.run_id)
            if existing is not None and (
                existing.user_id != user_id
                or existing.device_id_hash != device_id_hash
            ):
                raise ValueError("采集运行 ID 已属于其他用户或设备")
            if existing is None:
                created += 1
            self._runs[run.run_id] = _StoredRun(user_id, device_id_hash, run)
        return created

    async def list_runs(
        self,
        user_id: str,
        since: datetime | None = None,
    ) -> list[VivoCollectionRun]:
        runs = [
            item.run
            for item in self._runs.values()
            if item.user_id == user_id
            and (since is None or item.run.read_at >= since)
        ]
        return sorted(runs, key=lambda item: item.read_at)


class SQLAlchemyCollectionRunRepository(CollectionRunRepository):
    """PostgreSQL 采集运行摘要仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_runs(
        self,
        runs: list[VivoCollectionRun],
        user_id: str,
        device_id_hash: str,
    ) -> int:
        created = 0
        for run in runs:
            model = await self._session.get(VivoCollectionRunModel, run.run_id)
            if model is not None:
                if model.user_id != user_id or model.device_id_hash != device_id_hash:
                    raise ValueError("采集运行 ID 已属于其他用户或设备")
                _update_model(model, run)
                continue
            model = VivoCollectionRunModel(
                id=run.run_id,
                user_id=user_id,
                device_id_hash=device_id_hash,
                created_at=run.read_at,
                **run.model_dump(exclude={"run_id"}),
            )
            self._session.add(model)
            created += 1
        if runs:
            await self._session.commit()
        return created

    async def list_runs(
        self,
        user_id: str,
        since: datetime | None = None,
    ) -> list[VivoCollectionRun]:
        statement = select(VivoCollectionRunModel).where(
            VivoCollectionRunModel.user_id == user_id
        )
        if since is not None:
            statement = statement.where(VivoCollectionRunModel.read_at >= since)
        statement = statement.order_by(VivoCollectionRunModel.read_at)
        result = await self._session.scalars(statement)
        return [_to_schema(model) for model in result.all()]


def _update_model(model: VivoCollectionRunModel, run: VivoCollectionRun) -> None:
    for key, value in run.model_dump(exclude={"run_id"}).items():
        setattr(model, key, value)


def _to_schema(model: VivoCollectionRunModel) -> VivoCollectionRun:
    return VivoCollectionRun(
        run_id=model.id,
        source=model.source,
        read_at=model.read_at,
        status=model.status,
        provider_row_count=model.provider_row_count,
        valid_record_count=model.valid_record_count,
        first_measured_at=model.first_measured_at,
        last_measured_at=model.last_measured_at,
        app_version=model.app_version,
        provider_schema_hash=model.provider_schema_hash,
    )
