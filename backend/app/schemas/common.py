"""通用响应模型."""

from __future__ import annotations

from pydantic import BaseModel


class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "ok"


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
