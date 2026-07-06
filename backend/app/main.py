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
from app.database import Base, check_db, engine
from app.logging_config import setup_logging
from app.routers import auth, ca, crl, user_cert

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时创建数据库表 + 密钥库目录，关闭时释放引擎."""
    _ensure_keystore()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── 跨域配置 ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(ca.router)
app.include_router(user_cert.router)
app.include_router(crl.router)


@app.get("/api/health")
async def health_check():
    """存活 / 就绪探测（含数据库连通性检查）."""
    db_status = await check_db()
    return {
        "status": "ok" if db_status["status"] == "ok" else "degraded",
        "service": settings.app_name,
        "database": db_status,
    }


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
