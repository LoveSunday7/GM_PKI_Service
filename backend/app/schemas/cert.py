"""用户证书请求/响应模型."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CertIssueRequest(BaseModel):
    """签发用户证书的请求体."""

    user_name: str = Field(min_length=1, max_length=128, description="用户姓名（作为证书 Common Name）")
    email: str | None = Field(default=None, max_length=255, description="邮箱")
    organization: str | None = Field(default=None, max_length=255, description="组织名称")
    department: str | None = Field(default=None, max_length=255, description="部门")
    province: str | None = Field(default=None, max_length=128, description="省份")
    city: str | None = Field(default=None, max_length=128, description="城市")
    cert_type: str = Field(
        default="sign",
        pattern="^(sign|encrypt)$",
        description="证书类型：sign=签名证书, encrypt=加密证书",
    )
    validity_days: int = Field(default=365, ge=1, le=36500, description="证书有效期（天）")
    public_key_pem: str | None = Field(
        default=None, description="可选：PEM 格式公钥，不填则自动生成 SM2 密钥对"
    )


class CertIssueResponse(BaseModel):
    """用户证书签发成功响应."""

    success: bool = Field(description="是否成功")
    message: str = Field(description="结果描述")
    serial_number: str | None = Field(default=None, description="证书序列号（十六进制）")
    subject_dn: str | None = Field(default=None, description="证书主题 DN")
    cert_pem: str | None = Field(default=None, description="用户证书 PEM")
    public_key_pem: str | None = Field(default=None, description="用户公钥 PEM")
    key_pem: str | None = Field(default=None, description="用户私钥 PEM（仅自动生成密钥时返回）")
    root_cert_pem: str | None = Field(default=None, description="根证书 PEM")


class CertListResponse(BaseModel):
    """用户证书分页列表响应."""

    items: list[CertListItem] = Field(description="证书列表")
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页记录数")


class CertListItem(BaseModel):
    """用户证书列表项."""

    model_config = {"from_attributes": True}

    id: str = Field(description="记录 UUID")
    serial_number: str = Field(description="证书序列号")
    cert_type: str = Field(description="证书类型（sign/encrypt）")
    subject_dn: str = Field(description="主题 DN")
    user_name: str = Field(description="用户名")
    email: str | None = Field(default=None, description="邮箱")
    signature_algorithm: str = Field(description="签名算法")
    not_before: datetime = Field(description="生效时间")
    not_after: datetime = Field(description="到期时间")
    status: str = Field(description="证书状态（active/revoked）")
    created_at: datetime = Field(description="创建时间")


class CertDetailResponse(BaseModel):
    """用户证书详情."""

    model_config = {"from_attributes": True}

    id: str = Field(description="记录 UUID")
    serial_number: str = Field(description="证书序列号")
    cert_type: str = Field(description="证书类型")
    subject_dn: str = Field(description="主题 DN")
    issuer_dn: str = Field(description="签发者 DN")
    root_cert_serial: str = Field(description="签发此证书的根证书序列号")
    user_name: str = Field(description="用户名")
    email: str | None = Field(default=None, description="邮箱")
    organization: str | None = Field(default=None, description="组织")
    department: str | None = Field(default=None, description="部门")
    province: str | None = Field(default=None, description="省份")
    city: str | None = Field(default=None, description="城市")
    signature_algorithm: str = Field(description="签名算法")
    not_before: datetime = Field(description="生效时间")
    not_after: datetime = Field(description="到期时间")
    cert_pem: str = Field(description="证书 PEM 内容")
    public_key_pem: str = Field(description="公钥 PEM")
    key_size: int = Field(description="密钥长度（bit）")
    status: str = Field(description="证书状态")
    created_at: datetime = Field(description="创建时间")


class CertDownloadResponse(BaseModel):
    """证书下载响应."""
    cert_pem: str = Field(description="用户证书 PEM")
    key_pem: str | None = Field(default=None, description="私钥 PEM（如有）")
    root_cert_pem: str | None = Field(default=None, description="根证书 PEM（证书链）")
    filename: str = Field(description="建议文件名")


class CertStatusResponse(BaseModel):
    """证书撤销状态查询响应."""
    serial_number: str = Field(description="证书序列号")
    status: str = Field(description="证书状态（active/revoked）")
    revoked_at: datetime | None = Field(default=None, description="撤销时间")
    reason: str | None = Field(default=None, description="撤销原因")
