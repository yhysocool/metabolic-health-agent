"""阿里云健康数据接收入口，不加载本地 AI、LangGraph 或 FAISS。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, integrations, reports, user
from app.config import get_settings


settings = get_settings()
app = FastAPI(
    title="HealthEvent Ingestion API",
    version="0.6.0",
    description="衡康移动端健康数据接收与查询服务",
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
app.include_router(integrations.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)


@app.get("/healthz", tags=["system"])
async def health_check() -> dict[str, str]:
    """供反向代理和部署检查使用，不返回敏感配置。"""

    return {
        "status": "ok",
        "environment": settings.environment,
        "data_mode": (
            "synthetic_demo" if settings.repository_backend == "memory" else "database"
        ),
    }
