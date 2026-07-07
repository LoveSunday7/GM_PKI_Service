"""GM PKI Service — FastAPI 应用入口."""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

# 确保 backend 目录在 sys.path 中，支持 python app/main.py 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import check_db, engine
from app.exceptions import register_exception_handlers
from app.logging_config import setup_logging
from app.routers import admin, auth, ca, crl, dn_profile, ocsp, system, user_cert

# ── 初始化日志系统 ─────────────────────────────────────────────────
setup_logging()

logger = logging.getLogger(__name__)


def _ensure_keystore() -> None:
    """创建密钥库目录并校验读写权限."""
    keystore = settings.keystore_dir
    try:
        os.makedirs(keystore, exist_ok=True)
    except OSError as exc:
        logger.critical("无法创建密钥库目录 %s: %s", keystore, exc)
        raise

    # 权限检查：目录是否存在且可读写
    if not os.path.isdir(keystore):
        raise NotADirectoryError(f"密钥库路径不是目录: {keystore}")
    if not os.access(keystore, os.R_OK | os.W_OK):
        raise PermissionError(f"密钥库目录权限不足（需要读写权限）: {keystore}")

    logger.info("密钥库目录就绪: %s", keystore)


async def _run_migrations() -> None:
    """使用 Alembic 运行数据库迁移（替代 create_all）."""
    import asyncio

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)

    # alembic command.upgrade 是同步调用，内部 env.py 通过 asyncio.run() 执行异步迁移.
    # 在已有事件循环中需通过线程池隔离，避免 "cannot be called from a running event loop" 错误.
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    logger.info("数据库迁移完成")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动: 数据库迁移 + 密钥库目录 + CRL 自动签发；关闭: 释放引擎."""
    _ensure_keystore()
    await _run_migrations()

    # 启动 CRL 自动签发任务
    from app.routers.crl import start_auto_crl, stop_auto_crl
    start_auto_crl(settings.crl_validity_hours)

    yield

    stop_auto_crl()
    await engine.dispose()


# ── OpenAPI 标签元数据 ─────────────────────────────────────────────
_tags_metadata = [
    {"name": "认证", "description": "管理员登录、登出、Token 管理"},
    {"name": "管理员", "description": "管理员用户创建、查询、删除、密码管理"},
    {"name": "CA", "description": "根证书签发、查询、下载"},
    {"name": "用户证书", "description": "用户证书签发、查询、撤销状态"},
    {"name": "CRL", "description": "证书撤销、CRL 生成、查询、下载"},
    {"name": "OCSP", "description": "在线证书状态实时查询"},
    {"name": "系统", "description": "系统配置、数据库信息、日志管理"},
    {"name": "DN档案", "description": "用户 DN 身份档案管理（创建、查询、更新、删除）"},
]

app = FastAPI(
    title=settings.app_name,
    description="基于国密算法（SM2/SM3）的 PKI 体系数字证书认证系统",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_tags=_tags_metadata,
)

# ── 统一异常处理 ─────────────────────────────────────────────────
register_exception_handlers(app)

# ── 跨域配置 ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── 请求日志中间件 ───────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    elapsed = time.monotonic() - start
    logger.info(
        "%s %s → %d (%.3fs)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response

# ── 路由注册 ─────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(ca.router)
app.include_router(user_cert.router)
app.include_router(crl.router)
app.include_router(ocsp.router)
app.include_router(system.router)
app.include_router(dn_profile.router)


@app.get("/api/health")
async def health_check():
    """存活 / 就绪探测（含数据库连通性检查）."""
    db_status = await check_db()
    return {
        "status": "ok" if db_status["status"] == "ok" else "degraded",
        "service": settings.app_name,
        "database": db_status,
    }


@app.get("/")
async def root():
    """根路径重定向到 API 文档."""
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/api/docs")


# ── 直接运行入口 ─────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("BACKEND_PORT", "8000")),
        reload=settings.debug,
        log_level="info",
    )
