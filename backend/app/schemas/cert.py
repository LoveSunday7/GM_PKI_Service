"""用户证书请求/响应模型."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CertIssueRequest(BaseModel):
    """签发用户证书的请求体."""

    user_name: str = Field(max_length=128)
    email: str | None = Field(default=None, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    province: str | None = Field(default=None, max_length=128)
    city: str | None = Field(default=None, max_length=128)
    cert_type: str = Field(default="sign", pattern="^(sign|encrypt)$")
    validity_days: int = Field(default=365, ge=1, le=36500)
    public_key_pem: str | None = None  # 可选：导入已有公钥


class CertIssueResponse(BaseModel):
    success: bool
    message: str
    serial_number: str | None = None
    subject_dn: str | None = None
    cert_pem: str | None = None
    public_key_pem: str | None = None
    key_pem: str | None = None  # 仅签名证书返回私钥
    root_cert_pem: str | None = None


class CertListItem(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    serial_number: str
    cert_type: str
    subject_dn: str
    user_name: str
    email: str | None = None
    signature_algorithm: str
    not_before: datetime
    not_after: datetime
    status: str
    created_at: datetime


class CertDetailResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    serial_number: str
    cert_type: str
    subject_dn: str
    issuer_dn: str
    root_cert_serial: str
    user_name: str
    email: str | None = None
    organization: str | None = None
    department: str | None = None
    province: str | None = None
    city: str | None = None
    signature_algorithm: str
    not_before: datetime
    not_after: datetime
    cert_pem: str
    public_key_pem: str
    key_size: int
    status: str
    created_at: datetime


class CertDownloadResponse(BaseModel):
    cert_pem: str
    key_pem: str | None = None
    root_cert_pem: str | None = None
    filename: str


class CertStatusResponse(BaseModel):
    serial_number: str
    status: str  # active | revoked
    revoked_at: datetime | None = None
    reason: str | None = None
