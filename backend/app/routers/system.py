"""系统管理接口 — 系统配置查询、日志级别、数据库信息等."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import settings
from app.routers.auth import CurrentUser, get_current_user
from app.schemas.system import SystemConfigResponse

router = APIRouter(prefix="/api/system", tags=["系统"])


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
