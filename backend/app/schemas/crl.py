"""CRL 请求/响应模型."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ── 撤销原因枚举 ──────────────────────────────────────────────

REVOCATION_REASONS = [
    "unspecified",
    "keyCompromise",
    "affiliationChanged",
    "superseded",
    "cessationOfOperation",
]

REVOCATION_REASON_LABELS: dict[str, str] = {
    "unspecified": "未指定",
    "keyCompromise": "密钥泄露",
    "affiliationChanged": "隶属关系变更",
    "superseded": "已被取代",
    "cessationOfOperation": "停止运营",
}


class CRLRevokeRequest(BaseModel):
    """撤销证书的请求体."""

    cert_serial_number: str = Field(max_length=64, description="待撤销的证书序列号（十六进制）")
    reason: str = Field(
        default="unspecified",
        max_length=128,
        description=f"撤销原因: {' / '.join(REVOCATION_REASONS)}",
    )


class CRLRevokeResponse(BaseModel):
    """证书撤销成功响应."""

    success: bool = Field(description="是否成功")
    message: str = Field(description="结果描述")
    cert_serial_number: str | None = Field(default=None, description="被撤销的证书序列号")
    reason: str | None = Field(default=None, description="撤销原因")
    revoked_at: datetime | None = Field(default=None, description="撤销时间")


class CRLGenerateResponse(BaseModel):
    """CRL 生成成功响应."""

    success: bool = Field(description="是否成功")
    message: str = Field(description="结果描述")
    crl_number: int | None = Field(default=None, description="CRL 编号")
    this_update: datetime | None = Field(default=None, description="本次更新时间")
    next_update: datetime | None = Field(default=None, description="下次更新时间")
    revoked_count: int | None = Field(default=None, description="本次撤销的证书数量")
    crl_pem: str | None = Field(default=None, description="CRL PEM 内容")


class CRLQueryResponse(BaseModel):
    """CRL 查询响应."""

    model_config = {"from_attributes": True}

    crl_number: int = Field(description="CRL 编号")
    issuer_dn: str = Field(description="CRL 签发者 DN")
    this_update: datetime = Field(description="本次更新时间")
    next_update: datetime = Field(description="下次更新时间")
    signature_algorithm: str = Field(description="签名算法")
    revoked_count: int = Field(description="撤销的证书数量")
    crl_pem: str = Field(description="CRL PEM 内容")
    revoked_certificates: list[dict[str, Any]] = Field(description="撤销证书明细列表")
    created_at: datetime = Field(description="CRL 发布时间")


class CRLDownloadResponse(BaseModel):
    """CRL 文件下载响应."""

    crl_pem: str = Field(description="CRL PEM 内容")
    filename: str = Field(description="建议文件名")
