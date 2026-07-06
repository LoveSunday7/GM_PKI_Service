"""CRL 撤销记录与发布模型."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CRLRevocation(Base):
    __tablename__ = "crl_revocation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cert_serial_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(128), nullable=False, default="unspecified")
    revoked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CRLPublish(Base):
    __tablename__ = "crl_publish"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crl_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    issuer_dn: Mapped[str] = mapped_column(String(512), nullable=False)
    this_update: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    next_update: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    signature_algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    crl_pem: Mapped[str] = mapped_column(Text, nullable=False)
    revoked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
