"""Alembic 异步迁移环境 — 从 app.config 读取数据库 URL，自动发现模型."""

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── 导入项目配置与模型 ─────────────────────────────────────────
from app.config import settings as app_settings
from app.database import Base
import app.models  # noqa: F401 — 确保所有模型被导入以支持 autogenerate

config = context.config

# 将 app 的数据库 URL 设置到 alembic 配置中
config.set_main_option("sqlalchemy.url", app_settings.database_url)

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 目标元数据
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式 — 输出 SQL 脚本而非直接执行."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在线模式 — 使用异步引擎执行迁移."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
