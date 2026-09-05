"""用户档案 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_health_repository
from app.repositories.base import HealthRepository
from app.schemas.user import UserProfile, UserProfileCreate
from app.security import UserAccessDependency, ensure_user_scope


router = APIRouter(prefix="/user", tags=["user"])
RepositoryDependency = Annotated[HealthRepository, Depends(get_health_repository)]


@router.post("/profile", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
async def upsert_user_profile(
    profile: UserProfileCreate,
    repository: RepositoryDependency,
    principal: UserAccessDependency,
) -> UserProfile:
    """创建或按 ID 更新用户档案。"""

    ensure_user_scope(principal, profile.id)
    return await repository.save_user(profile)


@router.get("/profile/{user_id}", response_model=UserProfile)
async def get_user_profile(
    user_id: str,
    repository: RepositoryDependency,
    principal: UserAccessDependency,
) -> UserProfile:
    """读取单个用户档案。"""

    ensure_user_scope(principal, user_id)
    profile = await repository.get_user(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return profile
