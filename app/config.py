"""集中管理应用配置，避免业务模块直接读取环境变量。"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用级配置。

    所有环境变量使用 ``MHA_`` 前缀。默认选择内存 Mock 仓储，因此开发者在
    没有 PostgreSQL、LLM 服务和真实健康数据时也能启动完整 API。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MHA_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Metabolic Health Agent"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api"
    log_level: str = "INFO"
    cors_origins: list[str] = [
        "https://localhost",
        "http://localhost",
        "capacitor://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    repository_backend: Literal["memory", "sqlalchemy"] = "memory"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/metabolic_health"
    )
    seed_synthetic_data: bool = True
    demo_user_id: str = "00000000-0000-0000-0000-000000000001"
    cors_origin_regex: str | None = None

    llm_provider: Literal["deepseek", "qwen", "local"] = "local"
    deepseek_api_key: str | None = None
    qwen_api_key: str | None = None
    local_llm_base_url: str = "http://localhost:11434"

    health_lookback_days: int = Field(default=30, ge=1, le=365)
    rag_top_k: int = Field(default=3, ge=1, le=20)

    vivo_sync_enabled: bool = False
    vivo_sync_token: SecretStr | None = None
    vivo_enrollment_admin_token: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    """返回进程内共享的配置实例。"""

    return Settings()
