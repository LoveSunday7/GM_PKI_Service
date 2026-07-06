"""管理员用户管理接口 — 创建、查询、删除、修改密码."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.admin_user import AdminUser
from app.routers.auth import CurrentUser, get_current_user, hash_password
from app.schemas.admin import CreateAdminUserRequest, CreateAdminUserResponse

router = APIRouter(prefix="/api/admin", tags=["管理员"])
logger = logging.getLogger(__name__)


@router.post("/users", response_model=CreateAdminUserResponse)
async def create_admin_user(
    payload: CreateAdminUserRequest,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> CreateAdminUserResponse:
    """创建新的管理员用户（需登录）."""
    # 检查用户名是否已存在
    stmt = select(AdminUser).where(AdminUser.username == payload.username)
    result = await db.execute(stmt)
    if result.scalars().first() is not None:
        raise HTTPException(status_code=409, detail=f"用户名 {payload.username} 已存在")

    # 创建用户
    admin = AdminUser(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(admin)
    await db.flush()

    logger.info("管理员 %s 创建了新用户 %s（角色: %s）", _user.username, payload.username, payload.role)

    return CreateAdminUserResponse(
        success=True,
        message=f"管理员用户 {payload.username} 创建成功",
        username=payload.username,
        role=payload.role,
    )
