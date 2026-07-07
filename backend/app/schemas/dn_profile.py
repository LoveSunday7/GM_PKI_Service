"""DN 档案请求/响应模型."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DNProfileCreate(BaseModel):
    """创建 DN 档案."""
    name: str = Field(min_length=1, max_length=128, description="档案名称（唯一标识）")
    common_name: str = Field(min_length=1, max_length=128, description="Common Name")
    email: str | None = Field(default=None, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    province: str | None = Field(default=None, max_length=128)
    city: str | None = Field(default=None, max_length=128)
    country: str = Field(default="CN", min_length=2, max_length=2)


class DNProfileUpdate(BaseModel):
    """更新 DN 档案（全部可选）."""
    common_name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    province: str | None = Field(default=None, max_length=128)
    city: str | None = Field(default=None, max_length=128)
    country: str | None = Field(default=None, min_length=2, max_length=2)


class DNProfileItem(BaseModel):
    """DN 档案列表项."""
    model_config = {"from_attributes": True}

    id: str
    name: str
    common_name: str
    email: str | None = None
    organization: str | None = None
    department: str | None = None
    province: str | None = None
    city: str | None = None
    country: str
    created_at: datetime


class DNProfileResponse(BaseModel):
    """DN 档案操作响应."""
    success: bool
    message: str
    profile: DNProfileItem | None = None
