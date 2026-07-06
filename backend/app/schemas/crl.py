"""CRL 请求/响应模型."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CRLRevokeRequest(BaseModel):
    """撤销证书的请求体."""

    cert_serial_number: str = Field(max_length=64)
    reason: str = Field(default="unspecified", max_length=128)


class CRLRevokeResponse(BaseModel):
    success: bool
    message: str
    cert_serial_number: str | None = None
    reason: str | None = None
    revoked_at: datetime | None = None


class CRLGenerateResponse(BaseModel):
    success: bool
    message: str
    crl_number: int | None = None
    this_update: datetime | None = None
    next_update: datetime | None = None
    revoked_count: int | None = None
    crl_pem: str | None = None


class CRLQueryResponse(BaseModel):
    model_config = {"from_attributes": True}

    crl_number: int
    issuer_dn: str
    this_update: datetime
    next_update: datetime
    signature_algorithm: str
    revoked_count: int
    crl_pem: str
    revoked_certificates: list[dict[str, Any]]
    created_at: datetime


class CRLDownloadResponse(BaseModel):
    crl_pem: str
    filename: str
