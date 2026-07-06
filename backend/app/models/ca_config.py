"""CA 配置模型."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CAConfig(Base):
    __tablename__ = "ca_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ca_name: Mapped[str] = mapped_column(String(255), nullable=False, default="GM-PKI-CA")
    organization: Mapped[str] = mapped_column(String(255), nullable=False, default="Default Org")
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="CN")
    province: Mapped[str | None] = mapped_column(String(128))
    city: Mapped[str | None] = mapped_column(String(128))
    keystore_path: Mapped[str | None] = mapped_column(Text)
    signature_algorithm: Mapped[str] = mapped_column(String(64), nullable=False, default="SM3WITHSM2")
    validity_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3650)
    is_initialized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
