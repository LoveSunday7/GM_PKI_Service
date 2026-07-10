"""管理员用户管理接口 — 创建、查询、删除、修改密码."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.admin_user import AdminUser
from app.routers.auth import CurrentUser, hash_password, require_admin
from app.schemas.admin import (
    AdminUserListItem,
    ChangePasswordRequest,
    ChangePasswordResponse,
    CreateAdminUserRequest,
    CreateAdminUserResponse,
    DeleteAdminUserResponse,
)

router = APIRouter(prefix="/api/admin", tags=["管理员"])
logger = logging.getLogger(__name__)


@router.post("/users", response_model=CreateAdminUserResponse)
async def create_admin_user(
    payload: CreateAdminUserRequest,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_admin),
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


@router.get("/users", response_model=list[AdminUserListItem])
async def list_admin_users(
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_admin),
) -> list[AdminUserListItem]:
    """查询管理员用户列表（需登录）."""
    stmt = select(AdminUser).order_by(AdminUser.created_at.desc())
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [AdminUserListItem.model_validate(u) for u in users]


@router.delete("/users/{username}", response_model=DeleteAdminUserResponse)
async def delete_admin_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> DeleteAdminUserResponse:
    """删除管理员用户（需登录，禁止删除自己）."""
    # 禁止删除自己
    if username == current_user.username:
        raise HTTPException(status_code=403, detail="禁止删除自己的账户")

    # 查找用户
    stmt = select(AdminUser).where(AdminUser.username == username)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=404, detail=f"用户 {username} 不存在")

    await db.delete(user)
    await db.flush()

    logger.warning("管理员 %s 删除了用户 %s（角色: %s）", current_user.username, username, user.role)

    return DeleteAdminUserResponse(
        success=True,
        message=f"管理员用户 {username} 已删除",
        username=username,
    )


@router.put("/users/{username}/password", response_model=ChangePasswordResponse)
async def change_admin_password(
    username: str,
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> ChangePasswordResponse:
    """修改管理员用户密码（需登录）."""
    # 查找用户
    stmt = select(AdminUser).where(AdminUser.username == username)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=404, detail=f"用户 {username} 不存在")

    # 更新密码哈希
    user.password_hash = hash_password(payload.new_password)
    await db.flush()

    logger.info("管理员 %s 修改了用户 %s 的密码", current_user.username, username)

    return ChangePasswordResponse(
        success=True,
        message=f"用户 {username} 密码已更新",
        username=username,
    )
