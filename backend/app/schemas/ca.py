"""CA 根证书请求/响应模型."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CAInitRequest(BaseModel):
    """初始化 CA 并签发根证书的请求体."""

    ca_name: str = Field(
        default="GM-PKI-CA",
        max_length=255,
        description="CA 名称，将作为根证书 Common Name",
    )
    organization: str = Field(
        default="Default Org",
        max_length=255,
        description="组织名称",
    )
    country: str = Field(
        default="CN",
        min_length=2,
        max_length=2,
        description="两位 ISO 国家代码",
    )
    province: str | None = Field(default=None, max_length=128, description="省份")
    city: str | None = Field(default=None, max_length=128, description="城市")
    signature_algorithm: str = Field(
        default="SM3WITHSM2",
        max_length=64,
        description="签名算法，推荐 SM3WITHSM2",
    )
    validity_days: int = Field(
        default=3650,
        ge=1,
        le=36500,
        description="根证书有效期（天），默认 10 年",
    )
    key_size: int = Field(
        default=256,
        ge=256,
        le=512,
        description="SM2 密钥长度（bit）",
    )


class CAInitResponse(BaseModel):
    """初始化 CA 成功响应."""

    success: bool = Field(description="是否成功")
    message: str = Field(description="结果描述")
    serial_number: str | None = Field(default=None, description="根证书序列号（十六进制）")
    subject_dn: str | None = Field(default=None, description="根证书主题 DN")
    cert_pem: str | None = Field(default=None, description="根证书 PEM 内容")
    cert_path: str | None = Field(default=None, description="根证书密钥库文件路径")
    key_path: str | None = Field(default=None, description="根证书私钥密钥库文件路径")


class CAStatusResponse(BaseModel):
    """CA 初始化状态响应."""

    initialized: bool = Field(description="CA 是否已初始化")
    ca_name: str | None = Field(default=None, description="CA 名称（已初始化时有值）")
    organization: str | None = Field(default=None, description="组织名称")
    signature_algorithm: str | None = Field(default=None, description="签名算法")


class RootCertListItem(BaseModel):
    """根证书列表项."""

    model_config = {"from_attributes": True}

    id: str = Field(description="记录 UUID")
    serial_number: str = Field(description="证书序列号（十六进制）")
    subject_dn: str = Field(description="主题 DN")
    signature_algorithm: str = Field(description="签名算法")
    not_before: datetime = Field(description="生效时间")
    not_after: datetime = Field(description="到期时间")
    status: str = Field(description="证书状态（active/revoked）")
    created_at: datetime = Field(description="创建时间")


class RootCertDetailResponse(BaseModel):
    """根证书详情."""

    model_config = {"from_attributes": True}

    id: str = Field(description="记录 UUID")
    serial_number: str = Field(description="证书序列号（十六进制）")
    subject_dn: str = Field(description="主题 DN")
    issuer_dn: str = Field(description="签发者 DN（自签名为自身）")
    signature_algorithm: str = Field(description="签名算法")
    not_before: datetime = Field(description="生效时间")
    not_after: datetime = Field(description="到期时间")
    cert_pem: str = Field(description="证书 PEM 内容")
    key_size: int = Field(description="密钥长度（bit）")
    subject_key_identifier: str | None = Field(default=None, description="主题密钥标识符")
    authority_key_identifier: str | None = Field(default=None, description="授权密钥标识符")
    basic_constraints: str | None = Field(default=None, description="基本约束")
    key_usage: str | None = Field(default=None, description="密钥用途")
    status: str = Field(description="证书状态（active/revoked）")
    created_at: datetime = Field(description="创建时间")


class RootCertRevokeRequest(BaseModel):
    """根证书撤销请求."""

    reason: str = Field(
        default="unspecified",
        max_length=128,
        description="撤销原因：unspecified / keyCompromise / superseded / cessationOfOperation",
    )


class RootCertRevokeResponse(BaseModel):
    """根证书撤销响应."""

    success: bool = Field(description="是否成功")
    message: str = Field(description="结果描述")
    serial_number: str = Field(description="被撤销的根证书序列号")


class RootCertRenewRequest(BaseModel):
    """根证书续期请求."""

    validity_days: int = Field(
        default=3650,
        ge=1,
        le=36500,
        description="新证书有效期（天）",
    )


class RootCertRenewResponse(BaseModel):
    """根证书续期响应."""

    success: bool = Field(description="是否成功")
    message: str = Field(description="结果描述")
    old_serial_number: str = Field(description="旧根证书序列号")
    new_serial_number: str = Field(description="新根证书序列号")
    subject_dn: str = Field(description="主题 DN")
    cert_pem: str = Field(description="新根证书 PEM")
