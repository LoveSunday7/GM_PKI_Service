"""系统配置请求/响应模型."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# 支持的日志级别
VALID_LOG_LEVELS = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


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


class LogLevelRequest(BaseModel):
    """修改日志级别请求体."""

    level: VALID_LOG_LEVELS = Field(description="目标日志级别（DEBUG / INFO / WARNING / ERROR）")


class LogLevelResponse(BaseModel):
    """修改日志级别响应."""

    success: bool = Field(description="是否成功")
    previous_level: str = Field(description="修改前的日志级别")
    current_level: str = Field(description="修改后的日志级别")
    message: str = Field(description="结果描述")


class KeystoreFileItem(BaseModel):
    """密钥库单个文件信息."""

    name: str = Field(description="文件名")
    size_bytes: int = Field(description="文件大小（字节）")
    size_display: str = Field(description="文件大小（人类可读）")


class KeystoreInfoResponse(BaseModel):
    """密钥库信息响应 — GET /api/system/keystore-info."""

    path: str = Field(description="密钥库目录绝对路径")
    file_count: int = Field(description="文件数量")
    files: list[KeystoreFileItem] = Field(description="文件列表")
    total_size_bytes: int = Field(description="密钥库总占用（字节）")
    total_size_display: str = Field(description="密钥库总占用（人类可读）")


class ConfigUpdateRequest(BaseModel):
    """更新系统可动态修改的配置项（全部可选，仅更新提供的字段）."""

    ca_default_validity_days: int | None = Field(
        default=None,
        ge=1,
        le=36500,
        description="CA 根证书默认有效期（天）",
    )
    cert_default_validity_days: int | None = Field(
        default=None,
        ge=1,
        le=36500,
        description="用户证书默认有效期（天）",
    )
    crl_validity_hours: int | None = Field(
        default=None,
        ge=1,
        le=8760,
        description="CRL 有效期（小时）",
    )


class ConfigUpdateResponse(BaseModel):
    """更新系统配置响应."""

    success: bool = Field(description="是否成功")
    message: str = Field(description="结果描述")
    updated_fields: list[str] = Field(description="已更新的配置项列表")
    ca_default_validity_days: int = Field(description="当前 CA 根证书默认有效期（天）")
    cert_default_validity_days: int = Field(description="当前用户证书默认有效期（天）")
    crl_validity_hours: int = Field(description="当前 CRL 有效期（小时）")


class DatabaseTableInfo(BaseModel):
    """数据库单表信息."""

    name: str = Field(description="表名")
    row_count: int = Field(description="行数")


class DatabaseInfoResponse(BaseModel):
    """数据库详细信息响应 — GET /api/system/database."""

    database_type: str = Field(description="数据库类型（sqlite / mysql）")
    connected: bool = Field(description="数据库连接状态")
    tables: list[DatabaseTableInfo] = Field(description="表列表及行数")
    total_rows: int = Field(description="所有表总行数")


class LogQueryResponse(BaseModel):
    """日志查询响应 — GET /api/system/logs."""

    log_file: str = Field(description="日志文件路径")
    total_lines: int = Field(description="日志文件总行数")
    requested_lines: int = Field(description="请求返回的最大行数")
    level_filter: str | None = Field(default=None, description="日志级别过滤条件（若指定）")
    lines: list[str] = Field(description="匹配的日志行（最近 N 行，按时间升序）")
