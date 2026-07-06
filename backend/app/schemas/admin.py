"""管理员用户管理请求/响应模型."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# 管理员角色
ADMIN_ROLES = Literal["admin", "auditor", "operator"]


class CreateAdminUserRequest(BaseModel):
    """创建管理员用户请求体."""

    username: str = Field(
        min_length=1,
        max_length=64,
        description="用户名",
    )
    password: str = Field(
        min_length=6,
        max_length=128,
        description="密码（至少 6 位）",
    )
    role: ADMIN_ROLES = Field(
        default="admin",
        description="角色：admin / auditor / operator",
    )


class CreateAdminUserResponse(BaseModel):
    """创建管理员用户响应."""

    success: bool = Field(description="是否成功")
    message: str = Field(description="结果描述")
    username: str = Field(description="用户名")
    role: str = Field(description="角色")


class AdminUserListItem(BaseModel):
    """管理员用户列表项（不含密码哈希）."""

    model_config = {"from_attributes": True}

    id: str = Field(description="用户 UUID")
    username: str = Field(description="用户名")
    role: str = Field(description="角色")
    created_at: datetime = Field(description="创建时间")


class DeleteAdminUserResponse(BaseModel):
    """删除管理员用户响应."""

    success: bool = Field(description="是否成功")
    message: str = Field(description="结果描述")
    username: str = Field(description="被删除的用户名")
