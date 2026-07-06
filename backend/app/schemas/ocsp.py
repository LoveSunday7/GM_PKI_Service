"""OCSP 在线证书状态查询 — 请求/响应模型."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OCSPQueryRequest(BaseModel):
    """OCSP 查询请求 — 按 RFC 6960 简化格式."""
    cert_serial_number: str = Field(
        min_length=1, max_length=64,
        description="待查询的证书序列号（十六进制）",
    )


class OCSPQueryResponse(BaseModel):
    """OCSP 查询响应 — 实时返回证书状态."""
    success: bool = Field(description="查询是否成功执行")
    cert_serial_number: str = Field(description="查询的证书序列号")
    status: str = Field(description="证书状态: good / revoked / unknown")
    status_label: str = Field(description="状态中文标签: 正常 / 撤销 / 未知")
    this_update: datetime = Field(description="本次响应生成时间")
    next_update: datetime | None = Field(default=None, description="建议下次查询时间")
    revocation_time: datetime | None = Field(default=None, description="撤销时间（仅 revoked 时有值）")
    revocation_reason: str | None = Field(default=None, description="撤销原因（仅 revoked 时有值）")
    signature_algorithm: str | None = Field(default=None, description="响应签名算法")
    signature_value: str | None = Field(default=None, description="响应签名值（Base64）")
