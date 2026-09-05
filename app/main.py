"""FastAPI 应用入口与本地合成演示数据装配。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.synthetic_adapter import SyntheticHealthAdapter
from app.api import agent, health, integrations, reference, reports, user
from app.config import get_settings
from app.dependencies import get_memory_repository
from app.schemas.user import Gender, HealthGoal, UserProfileCreate


async def seed_synthetic_data() -> None:
    """幂等写入一个合成人物及其 30 天演示事件。"""

    settings = get_settings()
    repository = get_memory_repository()
    if await repository.get_user(settings.demo_user_id) is not None:
        return
    profile = UserProfileCreate(
        id=settings.demo_user_id,
        age=34,
        gender=Gender.UNDISCLOSED,
        height=167.3,
        weight=80,
        goal=HealthGoal.METABOLIC_HEALTH,
    )
    await repository.save_user(profile)
    for event in SyntheticHealthAdapter().collect(profile.id):
        await repository.add_event(event)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """仅在内存开发模式下初始化合成演示数据。"""

    settings = get_settings()
    if settings.repository_backend == "memory" and settings.seed_synthetic_data:
        await seed_synthetic_data()
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.6.0",
    description="面向亚健康成年人的健康管理辅助 Agent（本地合成数据验证与 vivo 接入骨架）",
    lifespan=lifespan,
)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )
app.include_router(user.router, prefix=settings.api_prefix)
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(agent.router, prefix=settings.api_prefix)
app.include_router(integrations.router, prefix=settings.api_prefix)
app.include_router(reference.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)


@app.get("/healthz", tags=["system"])
async def health_check() -> dict[str, str]:
    """不依赖数据库和外部模型的进程存活检查。"""

    return {
        "status": "ok",
        "environment": settings.environment,
        "data_mode": (
            "synthetic_demo" if settings.repository_backend == "memory" else "database"
        ),
    }
