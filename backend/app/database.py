"""异步数据库引擎、会话工厂和基类模型 — 支持 SQLite / MySQL 双模式."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def _is_sqlite(url: str) -> bool:
    """判断数据库 URL 是否为 SQLite."""
    return "sqlite" in url


def _build_engine_kwargs(url: str, debug: bool) -> dict:
    """根据数据库类型返回引擎配置参数."""
    if _is_sqlite(url):
        return dict(
            echo=debug,
            connect_args={"check_same_thread": False},
        )
    # MySQL / PostgreSQL 等
    return dict(
        echo=debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,          # 连接前检测有效性
        pool_recycle=3600,            # 每小时回收连接
    )


engine = create_async_engine(
    settings.database_url,
    **_build_engine_kwargs(settings.database_url, settings.debug),
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类."""

    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI 依赖注入：返回一个异步数据库会话.

    事务生命周期：
    - 路由正常返回 → 自动 commit
    - 路由抛出异常 → 自动 rollback
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db() -> dict:
    """数据库连通性检查 — 供健康检查或监控使用.

    返回:
        {"status": "ok", "backend": "sqlite"|"mysql", ...}
        或
        {"status": "error", "message": "..."}
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "backend": "sqlite" if _is_sqlite(settings.database_url) else "mysql",
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def get_backend() -> str:
    """返回当前数据库后端名称（sqlite / mysql）."""
    return "sqlite" if _is_sqlite(settings.database_url) else "mysql"
