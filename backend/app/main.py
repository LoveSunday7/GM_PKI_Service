"""GM PKI Service — FastAPI 应用入口."""

from __future__ import annotations

import sys
from pathlib import Path

# 确保 backend 目录在 sys.path 中，支持 python app/main.py 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.logging_config import setup_logging
from app.routers import auth, ca, crl, user_cert

# ── 初始化日志系统 ─────────────────────────────────────────────────
setup_logging()

import logging
import time

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时自动创建数据库表，关闭时释放引擎."""
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
    """存活 / 就绪探测."""
    return {"status": "ok", "service": settings.app_name}


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
