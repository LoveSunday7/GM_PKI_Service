"""日志系统搭建 — 级别配置、格式、按日期轮转、控制台+文件双输出."""

from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler

from app.config import settings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """初始化全局日志系统.

    - 日志级别由 settings.log_level 控制
    - 控制台输出：彩色友好的 StreamHandler
    - 文件输出：按天轮转（保留 30 天），自动创建日志目录
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # 避免重复添加（uvicorn reload 时会重新导入模块）
    if root_logger.handlers:
        return

    # ── 控制台 Handler ──────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(root_logger.level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # ── 文件 Handler（按天轮转）──────────────────────────────────
    os.makedirs(settings.log_dir, exist_ok=True)
    log_path = os.path.join(settings.log_dir, settings.log_file)

    file_handler = TimedRotatingFileHandler(
        filename=log_path,
        when="midnight",      # 每天午夜轮转
        interval=1,
        backupCount=30,       # 保留最近 30 天
        encoding="utf-8",
    )
    file_handler.setLevel(root_logger.level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    # 轮转后的文件命名后缀：app.log.2026-07-05
    file_handler.suffix = "%Y-%m-%d"
    root_logger.addHandler(file_handler)

    # 降低第三方库日志噪音
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)

    root_logger.info("日志系统初始化完成 (level=%s, log_dir=%s)", settings.log_level, settings.log_dir)
