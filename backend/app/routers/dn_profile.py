"""DN 档案管理接口 — 创建、查询、更新、删除."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.dn_profile import DNProfile
from app.routers.auth import CurrentUser, get_current_user
from app.schemas.dn_profile import (
    DNProfileCreate,
    DNProfileItem,
    DNProfileResponse,
    DNProfileUpdate,
)

router = APIRouter(prefix="/api/dn-profiles", tags=["DN档案"])
logger = logging.getLogger(__name__)


@router.post("", response_model=DNProfileResponse)
async def create_dn_profile(
    payload: DNProfileCreate,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> DNProfileResponse:
    """B011: 创建 DN 档案."""
    stmt = select(DNProfile).where(DNProfile.name == payload.name)
    if (await db.execute(stmt)).scalars().first():
        raise HTTPException(status_code=409, detail=f"档案名称 {payload.name} 已存在")

    profile = DNProfile(**payload.model_dump())
    db.add(profile)
    await db.flush()

    return DNProfileResponse(
        success=True,
        message=f"DN 档案 {payload.name} 创建成功",
        profile=DNProfileItem.model_validate(profile),
    )


@router.get("", response_model=list[DNProfileItem])
async def list_dn_profiles(
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> list[DNProfileItem]:
    """B011: 查询所有 DN 档案."""
    stmt = select(DNProfile).order_by(DNProfile.created_at.desc())
    result = await db.execute(stmt)
    return [DNProfileItem.model_validate(p) for p in result.scalars().all()]


@router.put("/{profile_id}", response_model=DNProfileResponse)
async def update_dn_profile(
    profile_id: str,
    payload: DNProfileUpdate,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> DNProfileResponse:
    """B011: 更新 DN 档案."""
    stmt = select(DNProfile).where(DNProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalars().first()
    if profile is None:
        raise HTTPException(status_code=404, detail="档案未找到")

    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, val)
    await db.flush()

    return DNProfileResponse(
        success=True,
        message=f"DN 档案已更新",
        profile=DNProfileItem.model_validate(profile),
    )


@router.delete("/{profile_id}", response_model=DNProfileResponse)
async def delete_dn_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> DNProfileResponse:
    """B011: 删除 DN 档案."""
    stmt = select(DNProfile).where(DNProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalars().first()
    if profile is None:
        raise HTTPException(status_code=404, detail="档案未找到")

    await db.delete(profile)
    await db.flush()

    return DNProfileResponse(
        success=True,
        message=f"DN 档案 {profile.name} 已删除",
    )
