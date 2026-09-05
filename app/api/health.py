"""统一健康事件写入与健康状态查询 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_health_repository
from app.repositories.base import HealthRepository
from app.schemas.health import (
    HealthEvent,
    HealthEventCreate,
    HealthEventList,
    HealthStatus,
)
from app.security import UserAccessDependency, ensure_user_scope
from app.services.health_service import HealthService


router = APIRouter(prefix="/health", tags=["health"])
RepositoryDependency = Annotated[HealthRepository, Depends(get_health_repository)]


@router.post("/event", response_model=HealthEvent, status_code=status.HTTP_201_CREATED)
async def create_health_event(
    event: HealthEventCreate,
    repository: RepositoryDependency,
    principal: UserAccessDependency,
) -> HealthEvent:
    """接收已标准化的单个健康事件。真实来源批量数据应先通过 Adapter。"""

    ensure_user_scope(principal, event.user_id)
    try:
        return await HealthService(repository).create_event(event)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/events/{user_id}", response_model=HealthEventList)
async def get_health_events(
    user_id: str,
    repository: RepositoryDependency,
    principal: UserAccessDependency,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> HealthEventList:
    """返回指定窗口内按时间升序排列的标准健康事件。"""

    ensure_user_scope(principal, user_id)
    try:
        events = await HealthService(repository).get_recent_events(user_id, days)
        return HealthEventList(
            user_id=user_id,
            window_days=days,
            count=len(events),
            items=events,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/status/{user_id}", response_model=HealthStatus)
async def get_health_status(
    user_id: str,
    repository: RepositoryDependency,
    principal: UserAccessDependency,
) -> HealthStatus:
    """返回最近 30 天的非诊断性健康管理状态。"""

    ensure_user_scope(principal, user_id)
    try:
        return await HealthService(repository).get_status(user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
