"""系统管理接口 — 系统配置查询、日志级别、数据库信息等."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.config import settings
from app.routers.auth import CurrentUser, get_current_user
from app.schemas.system import LogLevelRequest, LogLevelResponse, SystemConfigResponse

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
