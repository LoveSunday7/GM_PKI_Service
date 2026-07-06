"""根 CA 管理接口 — 初始化、查询、下载."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.ca_config import CAConfig
from app.models.root_cert import RootCert
from app.schemas.ca import (
    CAInitRequest,
    CAInitResponse,
    RootCertDetailResponse,
    RootCertListItem,
)
from app.routers.auth import CurrentUser, get_current_user
from app.services.crypto import (
    build_dn,
    build_self_signed_root_cert,
    generate_serial_number,
    generate_sm2_keypair,
)

router = APIRouter(prefix="/api/ca", tags=["CA"])


@router.post("/initialize", response_model=CAInitResponse)
async def initialize_ca(payload: CAInitRequest, db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)) -> CAInitResponse:
    """初始化 CA 并签发自签名根证书。

    系统仅允许存在一个 CA；重复调用将返回 409 错误。
    """
    # 检查 CA 是否已初始化
    stmt = select(CAConfig).where(CAConfig.is_initialized.is_(True))
    result = await db.execute(stmt)
    if result.scalars().first() is not None:
        raise HTTPException(status_code=409, detail="CA 已经初始化")

    # 生成根密钥对
    public_pem, private_pem, _ = generate_sm2_keypair()
    serial = generate_serial_number()

    # 构建主题 DN
    subject_dn = build_dn(
        common_name=payload.ca_name,
        organization=payload.organization,
        country=payload.country,
        province=payload.province,
        city=payload.city,
    )

    # 自签发根证书
    cert_pem = build_self_signed_root_cert(
        subject_dn=subject_dn,
        public_key_pem=public_pem,
        private_key_pem=private_pem,
        validity_days=payload.validity_days,
        serial_number=serial,
    )

    now = datetime.now(timezone.utc)

    # 持久化 CA 配置
    ca_config = CAConfig(
        ca_name=payload.ca_name,
        organization=payload.organization,
        country=payload.country,
        province=payload.province,
        city=payload.city,
        keystore_path=settings.keystore_dir,
        signature_algorithm=payload.signature_algorithm,
        validity_days=payload.validity_days,
        is_initialized=True,
    )
    db.add(ca_config)

    # 持久化根证书记录
    root_cert = RootCert(
        serial_number=serial,
        subject_dn=subject_dn,
        issuer_dn=subject_dn,
        signature_algorithm=payload.signature_algorithm,
        not_before=now,
        not_after=now.replace(year=now.year + payload.validity_days // 365),
        cert_pem=cert_pem,
        key_pem=private_pem,
        key_size=payload.key_size,
        status="active",
    )
    db.add(root_cert)
    await db.flush()

    return CAInitResponse(
        success=True,
        message="根 CA 证书签发成功",
        serial_number=serial,
        subject_dn=subject_dn,
        cert_pem=cert_pem,
    )


@router.get("/root-cert", response_model=list[RootCertListItem])
async def list_root_certs(db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)) -> list[RootCertListItem]:
    """查询所有根证书."""
    stmt = select(RootCert).order_by(RootCert.created_at.desc())
    result = await db.execute(stmt)
    certs = result.scalars().all()
    return [RootCertListItem.model_validate(c) for c in certs]


@router.get("/root-cert/{serial_number}", response_model=RootCertDetailResponse)
async def get_root_cert_detail(
    serial_number: str, db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)
) -> RootCertDetailResponse:
    """根据序列号查询根证书详情."""
    stmt = select(RootCert).where(RootCert.serial_number == serial_number)
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="根证书未找到")
    return RootCertDetailResponse.model_validate(cert)


@router.get("/root-cert/{serial_number}/download")
async def download_root_cert(serial_number: str, db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)):
    """下载根证书 PEM 文件."""
    from fastapi.responses import PlainTextResponse

    stmt = select(RootCert).where(RootCert.serial_number == serial_number)
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="根证书未找到")
    return PlainTextResponse(
        content=cert.cert_pem,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": f'attachment; filename="root_{serial_number}.pem"'},
    )


@router.get("/status")
async def ca_status(db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)):
    """查询 CA 初始化状态."""
    stmt = select(CAConfig).where(CAConfig.is_initialized.is_(True))
    result = await db.execute(stmt)
    config = result.scalars().first()
    if config is None:
        return {"initialized": False}
    return {
        "initialized": True,
        "ca_name": config.ca_name,
        "organization": config.organization,
        "signature_algorithm": config.signature_algorithm,
    }
