"""开发和测试使用的进程内 Mock 仓储。"""

import asyncio
from datetime import datetime

from app.repositories.base import HealthRepository
from app.schemas.health import HealthEvent, HealthEventCreate
from app.schemas.integration import (
    EventSyncCounts,
    IntegrationProvider,
    IntegrationSyncState,
)
from app.schemas.plan import HealthPlan, HealthPlanDraft
from app.schemas.user import UserProfile, UserProfileCreate


class InMemoryHealthRepository(HealthRepository):
    """无外部依赖的仓储实现。

    数据只在当前进程存活期间保留，绝不能作为生产数据持久化方案。
    """

    def __init__(self) -> None:
        self._users: dict[str, UserProfile] = {}
        self._events: dict[str, HealthEvent] = {}
        self._integration_states: dict[
            tuple[str, IntegrationProvider], IntegrationSyncState
        ] = {}
        self._plans: dict[str, HealthPlan] = {}
        self._lock = asyncio.Lock()

    async def save_user(self, profile: UserProfileCreate) -> UserProfile:
        stored = UserProfile.model_validate(profile.model_dump())
        async with self._lock:
            self._users[stored.id] = stored
        return stored

    async def get_user(self, user_id: str) -> UserProfile | None:
        return self._users.get(user_id)

    async def add_event(self, event: HealthEventCreate) -> HealthEvent:
        stored = HealthEvent(**event.model_dump())
        async with self._lock:
            self._events[stored.id] = stored
        return stored

    async def get_events(
        self, user_id: str, since: datetime | None = None
    ) -> list[HealthEvent]:
        events = [event for event in self._events.values() if event.user_id == user_id]
        if since is not None:
            events = [event for event in events if event.timestamp >= since]
        return sorted(events, key=lambda item: item.timestamp)

    async def sync_events(
        self,
        events: list[HealthEventCreate],
        state: IntegrationSyncState,
    ) -> EventSyncCounts:
        """在同一把锁内完成事件幂等写入和游标更新。"""

        created = updated = unchanged = 0
        async with self._lock:
            source_index = {
                (item.user_id, item.source, item.source_record_id): item
                for item in self._events.values()
                if item.source_record_id is not None
            }
            for event in events:
                key = (event.user_id, event.source, event.source_record_id)
                existing = source_index.get(key)
                if existing is None:
                    stored = HealthEvent(**event.model_dump())
                    self._events[stored.id] = stored
                    source_index[key] = stored
                    created += 1
                    continue

                replacement = HealthEvent(id=existing.id, **event.model_dump())
                if replacement == existing:
                    unchanged += 1
                    continue
                self._events[existing.id] = replacement
                source_index[key] = replacement
                updated += 1

            self._integration_states[(state.user_id, state.provider)] = state.model_copy(
                deep=True
            )
        return EventSyncCounts(created=created, updated=updated, unchanged=unchanged)

    async def get_integration_state(
        self, user_id: str, provider: IntegrationProvider
    ) -> IntegrationSyncState | None:
        state = self._integration_states.get((user_id, provider))
        return state.model_copy(deep=True) if state is not None else None

    async def save_plan(self, plan: HealthPlanDraft) -> HealthPlan:
        stored = HealthPlan(**plan.model_dump())
        async with self._lock:
            self._plans[stored.id] = stored
        return stored

    async def clear(self) -> None:
        """仅供测试隔离状态使用。"""

        async with self._lock:
            self._users.clear()
            self._events.clear()
            self._integration_states.clear()
            self._plans.clear()
