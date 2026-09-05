"""健康数据质量报告 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import (
    get_collection_run_repository,
    get_health_repository,
)
from app.repositories.base import HealthRepository
from app.repositories.collection_runs import CollectionRunRepository
from app.schemas.report import DataQualityReport
from app.security import UserAccessDependency, ensure_user_scope
from app.services.data_quality import DataQualityReportService


router = APIRouter(prefix="/reports", tags=["reports"])
RepositoryDependency = Annotated[HealthRepository, Depends(get_health_repository)]
CollectionRunDependency = Annotated[
    CollectionRunRepository, Depends(get_collection_run_repository)
]


@router.get("/data-quality/{user_id}", response_model=DataQualityReport)
async def get_data_quality_report(
    user_id: str,
    repository: RepositoryDependency,
    collection_repository: CollectionRunDependency,
    principal: UserAccessDependency,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> DataQualityReport:
    """返回指定用户在窗口内的确定性数据质量报告。"""

    ensure_user_scope(principal, user_id)
    try:
        if await repository.get_user(user_id) is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        return await DataQualityReportService(
            repository, collection_repository
        ).build(user_id, days)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
