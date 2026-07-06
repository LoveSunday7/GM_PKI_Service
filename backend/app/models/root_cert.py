"""根证书模型."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RootCert(Base):
    __tablename__ = "root_cert"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    serial_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    subject_dn: Mapped[str] = mapped_column(String(512), nullable=False)
    issuer_dn: Mapped[str] = mapped_column(String(512), nullable=False)
    signature_algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    not_before: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    not_after: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cert_pem: Mapped[str] = mapped_column(Text, nullable=False)
    key_pem: Mapped[str] = mapped_column(Text, nullable=False)  # 加密的私钥
    key_size: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    subject_key_identifier: Mapped[str | None] = mapped_column(String(128))
    authority_key_identifier: Mapped[str | None] = mapped_column(String(128))
    basic_constraints: Mapped[str | None] = mapped_column(String(128))
    key_usage: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
