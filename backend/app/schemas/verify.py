"""证书验证请求/响应模型."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CertVerifyRequest(BaseModel):
    """证书签名链验证请求：cert_pem 或 serial_number 二选一."""

    cert_pem: str | None = Field(default=None, description="待验证的证书 PEM 内容")
    serial_number: str | None = Field(default=None, description="待验证证书序列号")
    issuer_cert_pem: str | None = Field(default=None, description="签发者（上级）证书 PEM 内容；按序列号验证时可省略")
    show_chain: bool = Field(default=False, description="是否返回完整证书链")


class CertVerifyResponse(BaseModel):
    """证书签名链验证结果."""

    valid: bool = Field(description="签名是否有效")
    details: str = Field(description="验证结果描述")
    cert_subject: str = Field(description="待验证证书的主题 DN")
    issuer_subject: str = Field(description="签发者证书的主题 DN")
    serial_number: str = Field(description="待验证证书序列号")
    not_before: str | None = Field(default=None, description="证书生效时间")
    not_after: str | None = Field(default=None, description="证书到期时间")
    in_validity_period: bool = Field(default=False, description="是否在有效期内")
    chain: list[dict] | None = Field(default=None, description="可选：完整证书链")


class CRLVerifyRequest(BaseModel):
    """CRL 撤销验证请求."""

    cert_pem: str = Field(description="待验证的证书 PEM 内容")
    crl_pem: str = Field(description="CRL PEM 内容（可从 /api/crl/download 获取）")


class CRLVerifyResponse(BaseModel):
    """CRL 撤销验证结果."""

    revoked: bool = Field(description="证书是否已被撤销")
    reason: str | None = Field(default=None, description="撤销原因或验证说明")
    revocation_date: str | None = Field(default=None, description="撤销时间（ISO 8601）")
    error: str | None = Field(default=None, description="解析错误信息")
