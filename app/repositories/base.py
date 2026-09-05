"""健康数据仓储协议。服务与 Agent 只面向该抽象编程。"""

from datetime import datetime
from typing import Protocol

from app.schemas.health import HealthEvent, HealthEventCreate
from app.schemas.integration import (
    EventSyncCounts,
    IntegrationProvider,
    IntegrationSyncState,
)
from app.schemas.plan import HealthPlan, HealthPlanDraft
from app.schemas.user import UserProfile, UserProfileCreate


class HealthRepository(Protocol):
    """统一数据访问边界，便于替换内存、PostgreSQL 或测试实现。"""

    async def save_user(self, profile: UserProfileCreate) -> UserProfile: ...

    async def get_user(self, user_id: str) -> UserProfile | None: ...

    async def add_event(self, event: HealthEventCreate) -> HealthEvent: ...

    async def get_events(
        self, user_id: str, since: datetime | None = None
    ) -> list[HealthEvent]: ...

    async def sync_events(
        self,
        events: list[HealthEventCreate],
        state: IntegrationSyncState,
    ) -> EventSyncCounts: ...

    async def get_integration_state(
        self, user_id: str, provider: IntegrationProvider
    ) -> IntegrationSyncState | None: ...

    async def save_plan(self, plan: HealthPlanDraft) -> HealthPlan: ...
