"""公共研究数据参照查询 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_nhanes_reference_repository
from app.repositories.nhanes_reference import NHANESReferenceRepository
from app.schemas.reference import NHANESReferenceResponse


router = APIRouter(prefix="/research/nhanes", tags=["research-reference"])
ReferenceRepositoryDependency = Annotated[
    NHANESReferenceRepository, Depends(get_nhanes_reference_repository)
]


@router.get("/reference", response_model=NHANESReferenceResponse)
async def get_nhanes_reference(
    age: Annotated[int, Query(ge=18, le=100)],
    gender: Annotated[str, Query(min_length=1, max_length=16)],
    metric: Annotated[str, Query(min_length=1, max_length=96)],
    repository: ReferenceRepositoryDependency,
) -> NHANESReferenceResponse:
    """按年龄段、性别和指标返回聚合参照；不提供个体级记录。"""

    try:
        reference = repository.get_statistic(
            age=age,
            gender=gender,
            metric_code=metric,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="NHANES 聚合参照文件不可用") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="NHANES 聚合参照文件无效") from exc
    if reference is None:
        raise HTTPException(status_code=404, detail="没有匹配的 NHANES 聚合参照")
    return NHANESReferenceResponse.model_validate(reference.__dict__)
