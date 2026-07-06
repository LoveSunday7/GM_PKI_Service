"""认证接口 — 登录、登出、Token 管理，以及 JWT 认证依赖."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.admin_user import AdminUser
from app.models.token_blacklist import TokenBlacklist
from app.schemas.auth import LoginRequest, LoginResponse, LogoutResponse

router = APIRouter(prefix="/api/auth", tags=["认证"])

# ── Bearer Token 安全方案 ──────────────────────────────────────
_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    """当前认证用户信息."""
    username: str
    role: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """JWT 认证中间件 — 校验 Token 有效性、黑名单状态，返回当前用户.

    作为 FastAPI 依赖注入到需要认证的路由中.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="请先登录，缺少认证 Token")

    token = credentials.credentials

    # 1. 解码并校验 JWT 签名与过期时间
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 无效或已过期，请重新登录")

    jti = payload.get("jti")
    username = payload.get("sub", "unknown")
    role = payload.get("role", "admin")

    # 2. 检查 Token 是否已在黑名单中（已登出）
    if jti:
        stmt = select(TokenBlacklist).where(TokenBlacklist.token_jti == jti)
        result = await db.execute(stmt)
        if result.scalars().first() is not None:
            raise HTTPException(status_code=401, detail="Token 已登出，请重新登录")

    return CurrentUser(username=username, role=role)


def create_access_token(data: dict) -> tuple[str, str]:
    """使用配置的密钥和算法签发 JWT，返回 (token, jti)."""
    to_encode = data.copy()
    jti = str(uuid.uuid4())
    to_encode["jti"] = jti
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm), jti


def decode_token(token: str) -> dict:
    """解码并校验 JWT，返回 payload；校验失败时抛出 JWTError."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希值是否匹配."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def hash_password(password: str) -> str:
    """返回密码的 bcrypt 哈希."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    """管理员登录 — 用户名+密码，返回 JWT Token."""
    # 查找用户
    stmt = select(AdminUser).where(AdminUser.username == payload.username)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 签发 Token
    access_token, _ = create_access_token(data={"sub": user.username, "role": user.role})

    return LoginResponse(
        access_token=access_token,
        username=user.username,
        role=user.role,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    authorization: str = Header(..., description="Bearer <token>"),
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    """管理员登出 — 将当前 Token 加入黑名单，使其立即失效."""
    # 提取 Bearer Token
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="无效的认证头格式，期望 Bearer <token>")

    token = authorization[7:]

    # 解码 Token 获取 jti 和过期时间
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    jti = payload.get("jti")
    sub = payload.get("sub", "unknown")
    exp = payload.get("exp")

    if jti is None:
        raise HTTPException(status_code=401, detail="Token 缺少 jti 标识")

    # 检查是否已在黑名单中
    stmt = select(TokenBlacklist).where(TokenBlacklist.token_jti == jti)
    result = await db.execute(stmt)
    if result.scalars().first() is not None:
        return LogoutResponse(message="Token 已在此之前登出")

    # 加入黑名单
    expired_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc)
    blacklist_entry = TokenBlacklist(token_jti=jti, username=sub, expired_at=expired_at)
    db.add(blacklist_entry)
    await db.flush()

    return LogoutResponse()
