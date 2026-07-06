"""系统配置请求/响应模型."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SystemConfigResponse(BaseModel):
    """系统配置信息响应 — GET /api/system/config."""

    app_name: str = Field(description="应用名称")
    debug: bool = Field(description="调试模式")
    database_type: str = Field(description="数据库类型（sqlite / mysql）")
    keystore_dir: str = Field(description="密钥库目录路径")
    log_level: str = Field(description="当前日志级别（DEBUG/INFO/WARNING/ERROR）")
    ca_default_validity_days: int = Field(description="CA 根证书默认有效期（天）")
    cert_default_validity_days: int = Field(description="用户证书默认有效期（天）")
    crl_validity_hours: int = Field(description="CRL 有效期（小时）")
    default_signature_algorithm: str = Field(description="默认签名算法")
