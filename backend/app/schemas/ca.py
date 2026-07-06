"""CA 根证书请求/响应模型."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CAInitRequest(BaseModel):
    """初始化 CA 并签发根证书的请求体."""

    ca_name: str = Field(default="GM-PKI-CA", max_length=255)
    organization: str = Field(default="Default Org", max_length=255)
    country: str = Field(default="CN", min_length=2, max_length=2)
    province: str | None = None
    city: str | None = None
    signature_algorithm: str = Field(default="SM3WITHSM2", max_length=64)
    validity_days: int = Field(default=3650, ge=1, le=36500)
    key_size: int = Field(default=256, ge=256, le=512)


class CAInitResponse(BaseModel):
    success: bool
    message: str
    serial_number: str | None = None
    subject_dn: str | None = None
    cert_pem: str | None = None


class RootCertListItem(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    serial_number: str
    subject_dn: str
    signature_algorithm: str
    not_before: datetime
    not_after: datetime
    status: str
    created_at: datetime


class RootCertDetailResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    serial_number: str
    subject_dn: str
    issuer_dn: str
    signature_algorithm: str
    not_before: datetime
    not_after: datetime
    cert_pem: str
    key_size: int
    subject_key_identifier: str | None = None
    authority_key_identifier: str | None = None
    basic_constraints: str | None = None
    key_usage: str | None = None
    status: str
    created_at: datetime
