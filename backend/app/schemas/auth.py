"""认证相关 Pydantic 模型."""

from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """登录请求."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """登录成功响应."""
    success: bool = True
    message: str = "登录成功"
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class LogoutResponse(BaseModel):
    """登出响应."""
    success: bool = True
    message: str = "已成功登出"
