"""用户证书模型."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserCert(Base):
    __tablename__ = "user_cert"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    serial_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    cert_type: Mapped[str] = mapped_column(String(16), nullable=False, default="sign")  # sign | encrypt
    subject_dn: Mapped[str] = mapped_column(String(512), nullable=False)
    issuer_dn: Mapped[str] = mapped_column(String(512), nullable=False)
    root_cert_serial: Mapped[str] = mapped_column(String(64), nullable=False)
    issuer_cert_serial: Mapped[str | None] = mapped_column(String(64))
    owner_username: Mapped[str | None] = mapped_column(String(64), index=True)
    user_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    organization: Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(255))
    province: Mapped[str | None] = mapped_column(String(128))
    city: Mapped[str | None] = mapped_column(String(128))
    signature_algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    encryption_algorithm: Mapped[str] = mapped_column(String(64), nullable=False, default="SM2")
    not_before: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    not_after: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cert_pem: Mapped[str] = mapped_column(Text, nullable=False)
    key_pem: Mapped[str | None] = mapped_column(Text)  # 导入公钥时可为空
    public_key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    key_size: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")  # active | revoked
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
