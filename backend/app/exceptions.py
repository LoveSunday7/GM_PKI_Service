"""统一错误处理 — 业务异常类、错误码常量、全局异常处理器."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


# ═══════════════════════════════════════════════════════════════════
# 业务错误码
# ═══════════════════════════════════════════════════════════════════

class ErrorCode:
    """业务错误码常量."""
    # 认证
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_TOKEN_BLACKLISTED = "AUTH_TOKEN_BLACKLISTED"

    # CA
    CA_NOT_INITIALIZED = "CA_NOT_INITIALIZED"
    CA_ALREADY_INITIALIZED = "CA_ALREADY_INITIALIZED"
    CA_ROOT_CERT_NOT_FOUND = "CA_ROOT_CERT_NOT_FOUND"

    # 证书
    CERT_NOT_FOUND = "CERT_NOT_FOUND"
    CERT_ALREADY_REVOKED = "CERT_ALREADY_REVOKED"
    CERT_ISSUE_FAILED = "CERT_ISSUE_FAILED"

    # CRL
    CRL_EMPTY = "CRL_EMPTY"
    CRL_GENERATE_FAILED = "CRL_GENERATE_FAILED"

    # 通用
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"


# ═══════════════════════════════════════════════════════════════════
# 业务异常类
# ═══════════════════════════════════════════════════════════════════

class AppException(Exception):
    """应用级异常 — 所有业务异常由此派生.

    Attributes:
        error_code: 业务错误码（如 "CA_NOT_INITIALIZED"）
        message: 面向用户的错误描述
        http_status: HTTP 状态码
        detail: 附加详情（可选）
    """

    def __init__(
        self,
        error_code: str,
        message: str = "服务异常",
        http_status: int = 400,
        detail: Any = None,
    ):
        self.error_code = error_code
        self.message = message
        self.http_status = http_status
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppException):
    """资源未找到."""
    def __init__(self, message: str = "资源未找到", error_code: str = ErrorCode.NOT_FOUND):
        super().__init__(error_code=error_code, message=message, http_status=404)


class ConflictError(AppException):
    """资源冲突（如重复操作）."""
    def __init__(self, message: str = "资源冲突", error_code: str = "CONFLICT"):
        super().__init__(error_code=error_code, message=message, http_status=409)


class UnauthorizedError(AppException):
    """认证失败."""
    def __init__(self, message: str = "认证失败", error_code: str = ErrorCode.AUTH_INVALID_CREDENTIALS):
        super().__init__(error_code=error_code, message=message, http_status=401)


# ═══════════════════════════════════════════════════════════════════
# 全局异常处理器
# ═══════════════════════════════════════════════════════════════════

def _error_response(status_code: int, error_code: str, message: str, detail: Any = None) -> JSONResponse:
    """构建统一 JSON 错误响应."""
    body: dict[str, Any] = {
        "success": False,
        "error_code": error_code,
        "message": message,
    }
    if detail is not None:
        body["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


async def _app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    """处理 AppException 及其子类."""
    return _error_response(exc.http_status, exc.error_code, exc.message, exc.detail)


async def _http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """将 Starlette/FastAPI HTTPException 转为统一格式."""
    # 映射常见状态码到错误码
    code_map = {
        401: ErrorCode.AUTH_TOKEN_INVALID,
        403: "FORBIDDEN",
        404: ErrorCode.NOT_FOUND,
        409: "CONFLICT",
        422: ErrorCode.VALIDATION_ERROR,
    }
    error_code = code_map.get(exc.status_code, "HTTP_ERROR")
    return _error_response(exc.status_code, error_code, exc.detail)


async def _validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """处理 Pydantic 请求校验错误 — 提取字段级错误详情."""
    errors: list[dict[str, Any]] = []
    for error in exc.errors():
        errors.append({
            "field": " → ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    return _error_response(422, ErrorCode.VALIDATION_ERROR, "请求参数校验失败", errors)


async def _unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """兜底处理器 — 捕获所有未处理的异常，避免暴露内部细节."""
    import logging
    logger = logging.getLogger("app.exceptions")
    logger.exception("未处理的异常: %s", exc)
    return _error_response(500, ErrorCode.INTERNAL_ERROR, "服务器内部错误，请稍后重试")


def register_exception_handlers(app: FastAPI) -> None:
    """在 FastAPI 应用上注册所有全局异常处理器."""
    app.add_exception_handler(AppException, _app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
