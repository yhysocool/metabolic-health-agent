"""健康管理 Agent API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.agent.workflow import generate_health_plan
from app.dependencies import get_health_repository
from app.repositories.base import HealthRepository
from app.schemas.plan import HealthPlan


router = APIRouter(prefix="/agent", tags=["agent"])
RepositoryDependency = Annotated[HealthRepository, Depends(get_health_repository)]


@router.get("/plan/{user_id}", response_model=HealthPlan)
async def get_agent_plan(
    user_id: str, repository: RepositoryDependency
) -> HealthPlan:
    """执行完整 LangGraph 工作流并返回通过安全检查的计划。"""

    try:
        return await generate_health_plan(repository, user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

