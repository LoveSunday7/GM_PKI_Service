"""系统管理接口 — 系统配置查询、日志级别、数据库信息等."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.config import settings
from app.database import engine
from app.routers.auth import CurrentUser, get_current_user
from app.schemas.system import (
    ConfigUpdateRequest,
    ConfigUpdateResponse,
    DatabaseInfoResponse,
    DatabaseTableInfo,
    KeystoreFileItem,
    KeystoreInfoResponse,
    LogLevelRequest,
    LogLevelResponse,
    LogQueryResponse,
    SystemConfigResponse,
)

router = APIRouter(prefix="/api/system", tags=["系统"])
logger = logging.getLogger(__name__)


def _detect_database_type(database_url: str) -> str:
    """从数据库连接字符串中解析数据库类型."""
    url_lower = database_url.lower()
    if "mysql" in url_lower or "mariadb" in url_lower:
        return "mysql"
    if "postgresql" in url_lower:
        return "postgresql"
    return "sqlite"


def _format_size(size_bytes: int) -> str:
    """将字节数转为人类可读的格式."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


@router.get("/config", response_model=SystemConfigResponse)
async def get_system_config(
    _user: CurrentUser = Depends(get_current_user),
) -> SystemConfigResponse:
    """返回当前系统配置信息（需登录）."""
    return SystemConfigResponse(
        app_name=settings.app_name,
        debug=settings.debug,
        database_type=_detect_database_type(settings.database_url),
        keystore_dir=settings.keystore_dir,
        log_level=settings.log_level,
        ca_default_validity_days=settings.ca_default_validity_days,
        cert_default_validity_days=settings.cert_default_validity_days,
        crl_validity_hours=settings.crl_validity_hours,
        default_signature_algorithm=settings.default_signature_algorithm,
    )


@router.put("/log-level", response_model=LogLevelResponse)
async def update_log_level(
    payload: LogLevelRequest,
    _user: CurrentUser = Depends(get_current_user),
) -> LogLevelResponse:
    """动态修改日志级别，无需重启服务（需登录）."""
    previous_level = settings.log_level
    new_level = payload.level

    # 如果级别未变化，直接返回
    if previous_level == new_level:
        return LogLevelResponse(
            success=True,
            previous_level=previous_level,
            current_level=new_level,
            message=f"日志级别未变化，当前为 {new_level}",
        )

    level_value = getattr(logging, new_level)

    # 1. 更新配置中的日志级别
    settings.log_level = new_level

    # 2. 更新根 logger 及其所有 handler 的级别
    root_logger = logging.getLogger()
    root_logger.setLevel(level_value)
    for handler in root_logger.handlers:
        handler.setLevel(level_value)

    # 3. 记录变更
    logger.warning("日志级别由 %s 变更为 %s", previous_level, new_level)

    return LogLevelResponse(
        success=True,
        previous_level=previous_level,
        current_level=new_level,
        message=f"日志级别已从 {previous_level} 切换为 {new_level}",
    )


@router.get("/keystore-info", response_model=KeystoreInfoResponse)
async def get_keystore_info(
    _user: CurrentUser = Depends(get_current_user),
) -> KeystoreInfoResponse:
    """返回密钥库目录路径、文件列表及磁盘占用（需登录）."""
    keystore_path = settings.keystore_dir

    files: list[KeystoreFileItem] = []
    total_size = 0

    if os.path.isdir(keystore_path):
        for entry in sorted(os.scandir(keystore_path), key=lambda e: e.name):
            if entry.is_file():
                size = entry.stat().st_size
                total_size += size
                files.append(KeystoreFileItem(
                    name=entry.name,
                    size_bytes=size,
                    size_display=_format_size(size),
                ))

    return KeystoreInfoResponse(
        path=keystore_path,
        file_count=len(files),
        files=files,
        total_size_bytes=total_size,
        total_size_display=_format_size(total_size),
    )


@router.put("/config", response_model=ConfigUpdateResponse)
async def update_system_config(
    payload: ConfigUpdateRequest,
    _user: CurrentUser = Depends(get_current_user),
) -> ConfigUpdateResponse:
    """更新可动态修改的系统配置项（需登录）。

    仅更新请求中提供了的字段，未提供的字段保持不变。
    可修改项：CA 默认有效期、证书默认有效期、CRL 有效期。
    """
    updated_fields: list[str] = []

    if payload.ca_default_validity_days is not None:
        old_val = settings.ca_default_validity_days
        settings.ca_default_validity_days = payload.ca_default_validity_days
        logger.info("CA 默认有效期: %s → %s 天", old_val, payload.ca_default_validity_days)
        updated_fields.append("ca_default_validity_days")

    if payload.cert_default_validity_days is not None:
        old_val = settings.cert_default_validity_days
        settings.cert_default_validity_days = payload.cert_default_validity_days
        logger.info("证书默认有效期: %s → %s 天", old_val, payload.cert_default_validity_days)
        updated_fields.append("cert_default_validity_days")

    if payload.crl_validity_hours is not None:
        old_val = settings.crl_validity_hours
        settings.crl_validity_hours = payload.crl_validity_hours
        logger.info("CRL 有效期: %s → %s 小时", old_val, payload.crl_validity_hours)
        updated_fields.append("crl_validity_hours")

    message = (
        f"已更新 {len(updated_fields)} 项配置：" + ", ".join(updated_fields)
        if updated_fields
        else "未提供需要更新的配置项，无变更"
    )

    return ConfigUpdateResponse(
        success=True,
        message=message,
        updated_fields=updated_fields,
        ca_default_validity_days=settings.ca_default_validity_days,
        cert_default_validity_days=settings.cert_default_validity_days,
        crl_validity_hours=settings.crl_validity_hours,
    )


# 需从表清单中排除的内部表
_EXCLUDED_TABLES = {"alembic_version", "sqlite_sequence"}


async def _get_table_names(conn: AsyncConnection) -> list[str]:
    """获取数据库中的用户表名列表（排除内部表）."""
    def _sync_tables(sync_conn):
        inspector = inspect(sync_conn)
        return inspector.get_table_names()

    all_tables = await conn.run_sync(_sync_tables)
    return [t for t in all_tables if t not in _EXCLUDED_TABLES]


@router.get("/database", response_model=DatabaseInfoResponse)
async def get_database_info(
    _user: CurrentUser = Depends(get_current_user),
) -> DatabaseInfoResponse:
    """返回数据库详细信息：类型、连接状态、表列表及行数（需登录）."""
    db_type = _detect_database_type(settings.database_url)
    connected = False
    tables: list[DatabaseTableInfo] = []
    total_rows = 0

    try:
        async with engine.connect() as conn:
            connected = True
            table_names = await _get_table_names(conn)

            for tname in sorted(table_names):
                result = await conn.execute(text(f'SELECT COUNT(*) FROM "{tname}"'))
                row_count: int = result.scalar()  # type: ignore[assignment]
                tables.append(DatabaseTableInfo(name=tname, row_count=row_count))
                total_rows += row_count
    except Exception:
        logger.exception("查询数据库信息失败")
        connected = False

    return DatabaseInfoResponse(
        database_type=db_type,
        connected=connected,
        tables=tables,
        total_rows=total_rows,
    )


@router.get("/logs", response_model=LogQueryResponse)
async def get_logs(
    _user: CurrentUser = Depends(get_current_user),
    lines: int = Query(default=100, ge=1, le=10000, description="返回最近 N 行"),
    level: str | None = Query(default=None, description="按日志级别过滤（DEBUG/INFO/WARNING/ERROR）"),
) -> LogQueryResponse:
    """返回最近 N 行日志内容，支持按级别过滤（需登录）."""
    log_path = os.path.join(settings.log_dir, settings.log_file)

    # 读取全部日志行
    all_lines: list[str] = []
    if os.path.isfile(log_path):
        with open(log_path, encoding="utf-8") as fh:
            all_lines = fh.readlines()

    total_lines = len(all_lines)

    # 按级别过滤
    if level:
        level_upper = level.upper()
        all_lines = [ln for ln in all_lines if f"| {level_upper}" in ln]

    # 取最近 N 行（去除尾部换行符）
    recent = [ln.rstrip("\n") for ln in all_lines[-lines:]]

    return LogQueryResponse(
        log_file=log_path,
        total_lines=total_lines,
        requested_lines=lines,
        level_filter=level.upper() if level else None,
        lines=recent,
    )
