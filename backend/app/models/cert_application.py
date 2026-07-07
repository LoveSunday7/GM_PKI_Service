"""证书申请模型 — RA 审核工作流."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CertApplication(Base):
    __tablename__ = "cert_application"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    organization: Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(255))
    province: Mapped[str | None] = mapped_column(String(128))
    city: Mapped[str | None] = mapped_column(String(128))
    cert_type: Mapped[str] = mapped_column(String(16), nullable=False, default="sign")
    validity_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    public_key_pem: Mapped[str | None] = mapped_column(Text)

    # 审核状态
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending / approved / rejected
    reject_reason: Mapped[str | None] = mapped_column(Text)

    # 审核人信息
    applied_by: Mapped[str] = mapped_column(String(64), nullable=False)  # 提交人用户名
    reviewed_by: Mapped[str | None] = mapped_column(String(64))  # 审核人用户名

    # 签发结果
    issued_cert_serial: Mapped[str | None] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
