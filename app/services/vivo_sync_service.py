"""vivo 健康记录的增量同步应用服务。"""

from hashlib import sha256

from app.adapters.vivo_adapter import VivoAdapter
from app.repositories.base import HealthRepository
from app.repositories.collection_runs import CollectionRunRepository
from app.schemas.integration import (
    IntegrationProvider,
    IntegrationSyncState,
    VivoSyncRequest,
    VivoSyncResult,
    VivoSyncStatus,
)


class VivoSyncService:
    """编排桥接记录校验、标准化、幂等写入和同步状态保存。"""

    def __init__(self, repository: HealthRepository) -> None:
        self._repository = repository
        self._adapter = VivoAdapter()

    async def sync(
        self,
        request: VivoSyncRequest,
        collection_repository: CollectionRunRepository | None = None,
    ) -> VivoSyncResult:
        if await self._repository.get_user(request.user_id) is None:
            raise LookupError(f"用户 {request.user_id} 不存在")

        record_ids = [record.record_id for record in request.records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("同一同步批次不能包含重复的 record_id")

        raw_records = [record.model_dump() for record in request.records]
        events = self._adapter.normalize(request.user_id, raw_records)
        self._adapter.validate(events)
        state = IntegrationSyncState(
            user_id=request.user_id,
            provider=IntegrationProvider.VIVO,
            device_id_hash=sha256(request.device_id.encode("utf-8")).hexdigest(),
            cursor=request.cursor,
            last_record_count=len(events),
        )
        counts = await self._repository.sync_events(events, state)
        collection_runs_created = 0
        if collection_repository is not None and request.collection_runs:
            collection_runs_created = await collection_repository.save_runs(
                request.collection_runs,
                request.user_id,
                state.device_id_hash,
            )
        return VivoSyncResult(
            batch_id=request.batch_id,
            user_id=request.user_id,
            received=len(events),
            created=counts.created,
            updated=counts.updated,
            unchanged=counts.unchanged,
            cursor=state.cursor,
            last_success_at=state.last_success_at,
            collection_runs_received=len(request.collection_runs),
            collection_runs_created=collection_runs_created,
        )

    async def get_status(self, user_id: str) -> VivoSyncStatus:
        if await self._repository.get_user(user_id) is None:
            raise LookupError(f"用户 {user_id} 不存在")
        state = await self._repository.get_integration_state(
            user_id, IntegrationProvider.VIVO
        )
        if state is None:
            return VivoSyncStatus(user_id=user_id, connected=False)
        return VivoSyncStatus(
            user_id=user_id,
            connected=True,
            cursor=state.cursor,
            last_success_at=state.last_success_at,
            last_record_count=state.last_record_count,
        )
