"""应用配置 — 从环境变量加载."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用全局设置，通过 .env 或环境变量配置."""

    # ── 应用 ──────────────────────────────────────────────────────
    app_name: str = "GM PKI Service"
    debug: bool = False

    # ── 数据库 ────────────────────────────────────────────────────
    # 开发环境: sqlite+aiosqlite:///./data.db
    # 生产环境: mysql+aiomysql://user:pass@host:3306/gm_pki
    database_url: str = "sqlite+aiosqlite:///./data.db"

    # ── 密钥库 ────────────────────────────────────────────────────
    keystore_dir: str = os.path.join(Path(__file__).resolve().parent.parent, "keystore")

    # ── CA 默认配置 ──────────────────────────────────────────────
    ca_default_validity_days: int = 3650  # 10年
    cert_default_validity_days: int = 365  # 1年
    crl_validity_hours: int = 24
    default_signature_algorithm: str = "SM3WITHSM2"

    # ── CORS ─────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
