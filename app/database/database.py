"""SQLAlchemy 异步引擎与会话工厂。

模块只负责连接生命周期，不包含查询和业务规则。默认 Mock 模式不会建立数据库连接。
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""


settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """为一次请求提供独立事务会话。"""

    async with AsyncSessionFactory() as session:
        yield session

