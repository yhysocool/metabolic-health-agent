"""PostgreSQL/SQLAlchemy 仓储实现。"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    HealthEventModel,
    HealthPlanModel,
    IntegrationSyncStateModel,
    UserProfileModel,
)
from app.repositories.base import HealthRepository
from app.schemas.health import HealthEvent, HealthEventCreate
from app.schemas.integration import (
    EventSyncCounts,
    IntegrationProvider,
    IntegrationSyncState,
)
from app.schemas.plan import HealthPlan, HealthPlanDraft
from app.schemas.user import UserProfile, UserProfileCreate


class SQLAlchemyHealthRepository(HealthRepository):
    """将 ORM 细节限制在基础设施层，事务按单次写操作提交。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_user(self, profile: UserProfileCreate) -> UserProfile:
        existing = await self._session.get(UserProfileModel, profile.id)
        if existing is None:
            existing = UserProfileModel(**profile.model_dump())
            self._session.add(existing)
        else:
            for key, value in profile.model_dump().items():
                setattr(existing, key, value)
        await self._session.commit()
        await self._session.refresh(existing)
        return UserProfile.model_validate(existing)

    async def get_user(self, user_id: str) -> UserProfile | None:
        model = await self._session.get(UserProfileModel, user_id)
        return UserProfile.model_validate(model) if model else None

    async def add_event(self, event: HealthEventCreate) -> HealthEvent:
        model = HealthEventModel(**HealthEvent(**event.model_dump()).model_dump())
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return HealthEvent.model_validate(model)

    async def get_events(
        self, user_id: str, since: datetime | None = None
    ) -> list[HealthEvent]:
        statement = select(HealthEventModel).where(HealthEventModel.user_id == user_id)
        if since is not None:
            statement = statement.where(HealthEventModel.timestamp >= since)
        statement = statement.order_by(HealthEventModel.timestamp)
        result = await self._session.scalars(statement)
        return [HealthEvent.model_validate(model) for model in result.all()]

    async def sync_events(
        self,
        events: list[HealthEventCreate],
        state: IntegrationSyncState,
    ) -> EventSyncCounts:
        """在一个数据库事务中写入事件并推进同步游标。"""

        created = updated = unchanged = 0
        try:
            for event in events:
                statement = select(HealthEventModel).where(
                    HealthEventModel.user_id == event.user_id,
                    HealthEventModel.source == event.source,
                    HealthEventModel.source_record_id == event.source_record_id,
                )
                existing = await self._session.scalar(statement)
                if existing is None:
                    stored = HealthEvent(**event.model_dump())
                    self._session.add(HealthEventModel(**stored.model_dump()))
                    created += 1
                    continue

                current = HealthEvent.model_validate(existing)
                replacement = HealthEvent(id=current.id, **event.model_dump())
                if replacement == current:
                    unchanged += 1
                    continue
                for key, value in event.model_dump().items():
                    setattr(existing, key, value)
                updated += 1

            state_model = await self._session.get(
                IntegrationSyncStateModel,
                {"user_id": state.user_id, "provider": state.provider},
            )
            if state_model is None:
                self._session.add(IntegrationSyncStateModel(**state.model_dump()))
            else:
                for key, value in state.model_dump().items():
                    setattr(state_model, key, value)
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        return EventSyncCounts(created=created, updated=updated, unchanged=unchanged)

    async def get_integration_state(
        self, user_id: str, provider: IntegrationProvider
    ) -> IntegrationSyncState | None:
        model = await self._session.get(
            IntegrationSyncStateModel,
            {"user_id": user_id, "provider": provider},
        )
        return IntegrationSyncState.model_validate(model, from_attributes=True) if model else None

    async def save_plan(self, plan: HealthPlanDraft) -> HealthPlan:
        stored = HealthPlan(**plan.model_dump())
        model = HealthPlanModel(**stored.model_dump())
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return HealthPlan.model_validate(model)
