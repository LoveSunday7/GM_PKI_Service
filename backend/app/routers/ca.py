"""根 CA 管理接口 — 初始化、查询、下载、撤销、续期、重置."""

from __future__ import annotations

import os as _os

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.ca_config import CAConfig
from app.models.cert_application import CertApplication
from app.models.crl import CRLPublish, CRLRevocation
from app.models.revocation_application import RevocationApplication
from app.models.root_cert import RootCert
from app.models.user_cert import UserCert
from app.schemas.ca import (
    CAInitRequest,
    CAInitResponse,
    CAStatusResponse,
    RootCertDetailResponse,
    RootCertListItem,
    RootCertRenewRequest,
    RootCertRenewResponse,
    RootCertRevokeRequest,
    RootCertRevokeResponse,
)
from app.routers.auth import CurrentUser, get_current_user
from app.services.crypto import (
    build_dn,
    build_self_signed_root_cert,
    generate_serial_number,
    generate_sm2_keypair,
    save_keystore_file,
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
        signature_algorithm=payload.signature_algorithm,
    )

    now = datetime.now(timezone.utc)

    # 将根证书和私钥保存为密钥库文件
    cert_path = save_keystore_file(f"root_{serial}.pem", cert_pem)
    key_path = save_keystore_file(f"root_{serial}.key", private_pem)

    # 持久化 CA 配置 — 更新已有记录或创建新记录
    ca_config_stmt = select(CAConfig).order_by(CAConfig.created_at.desc()).limit(1)
    ca_result = await db.execute(ca_config_stmt)
    ca_config = ca_result.scalars().first()

    if ca_config and not ca_config.is_initialized:
        # 复用系统设置中已配置的 CA 信息
        ca_config.ca_name = payload.ca_name
        ca_config.organization = payload.organization
        ca_config.country = payload.country
        ca_config.province = payload.province
        ca_config.city = payload.city
        ca_config.keystore_path = cert_path + "\n" + key_path
        ca_config.signature_algorithm = payload.signature_algorithm
        ca_config.validity_days = payload.validity_days
        ca_config.is_initialized = True
    else:
        ca_config = CAConfig(
            ca_name=payload.ca_name,
            organization=payload.organization,
            country=payload.country,
            province=payload.province,
            city=payload.city,
            keystore_path=cert_path + "\n" + key_path,
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
        not_after=now + timedelta(days=payload.validity_days),
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
        cert_path=cert_path,
        key_path=key_path,
    )


@router.post("/reset")
async def reset_ca(db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)):
    """重置 CA — 清空所有证书、申请、撤销记录及密钥库文件，回到未初始化状态。"""
    import logging
    logger = logging.getLogger(__name__)

    # 删除所有证书相关数据（注意顺序：先删子表再删父表）
    await db.execute(delete(RevocationApplication))
    await db.execute(delete(CRLRevocation))
    await db.execute(delete(CRLPublish))
    await db.execute(delete(CertApplication))
    await db.execute(delete(UserCert))
    await db.execute(delete(RootCert))

    # 重置 CA 配置
    await db.execute(delete(CAConfig))

    # 清空密钥库文件
    keystore_dir = settings.keystore_dir
    if _os.path.isdir(keystore_dir):
        for fname in _os.listdir(keystore_dir):
            fpath = _os.path.join(keystore_dir, fname)
            if _os.path.isfile(fpath):
                _os.remove(fpath)

    await db.commit()
    logger.warning("管理员 %s 重置了 CA，所有证书数据已清空", _user.username)
    return {"success": True, "message": "CA 已重置，所有证书和密钥库文件已清空"}


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
    import os as _os

    stmt = select(RootCert).where(RootCert.serial_number == serial_number)
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="根证书未找到")

    # 构造密钥库文件路径
    cert_path = _os.path.join(settings.keystore_dir, f"root_{cert.serial_number}.pem")
    key_path = _os.path.join(settings.keystore_dir, f"root_{cert.serial_number}.key")

    resp = RootCertDetailResponse.model_validate(cert)
    resp.cert_path = cert_path
    resp.key_path = key_path
    return resp


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


@router.get("/status", response_model=CAStatusResponse)
async def ca_status(db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)):
    """查询 CA 初始化状态."""
    stmt = select(CAConfig).where(CAConfig.is_initialized.is_(True))
    result = await db.execute(stmt)
    config = result.scalars().first()
    if config is None:
        return CAStatusResponse(initialized=False)
    return CAStatusResponse(
        initialized=True,
        ca_name=config.ca_name,
        organization=config.organization,
        signature_algorithm=config.signature_algorithm,
    )


@router.post("/root-cert/{serial_number}/revoke", response_model=RootCertRevokeResponse)
async def revoke_root_cert(
    serial_number: str,
    payload: RootCertRevokeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RootCertRevokeResponse:
    """撤销根证书（A004）.

    将指定根证书状态标记为 revoked。禁止撤销所有活跃根证书。
    """
    stmt = select(RootCert).where(RootCert.serial_number == serial_number)
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="根证书未找到")
    if cert.status == "revoked":
        raise HTTPException(status_code=409, detail="根证书已被撤销")

    # 检查是否是唯一的活跃根证书
    active_stmt = select(RootCert).where(RootCert.status == "active")
    active_result = await db.execute(active_stmt)
    active_certs = active_result.scalars().all()
    if len(active_certs) == 1 and active_certs[0].serial_number == serial_number:
        raise HTTPException(status_code=400, detail="无法撤销唯一的活跃根证书，请先生成新的根证书")

    cert.status = "revoked"
    await db.flush()

    import logging
    logger = logging.getLogger(__name__)
    logger.warning("管理员 %s 撤销了根证书 %s（原因: %s）", current_user.username, serial_number, payload.reason)

    return RootCertRevokeResponse(
        success=True,
        message=f"根证书 {serial_number} 已撤销（原因: {payload.reason}）",
        serial_number=serial_number,
    )


@router.post("/root-cert/{serial_number}/renew", response_model=RootCertRenewResponse)
async def renew_root_cert(
    serial_number: str,
    payload: RootCertRenewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RootCertRenewResponse:
    """续期根证书（A005）.

    使用现有根证书的密钥对签发一张新的根证书（相同 DN、相同密钥、新的有效期）。
    旧证书保持 active 状态，后续可手动撤销。
    """
    stmt = select(RootCert).where(RootCert.serial_number == serial_number)
    result = await db.execute(stmt)
    old_cert = result.scalars().first()
    if old_cert is None:
        raise HTTPException(status_code=404, detail="根证书未找到")
    if old_cert.status != "active":
        raise HTTPException(status_code=400, detail="只能续期活跃状态的根证书")

    # 从旧证书提取公钥 PEM
    from cryptography import x509 as crypto_x509
    from cryptography.hazmat.primitives import serialization as crypto_serialization

    old_x509 = crypto_x509.load_pem_x509_certificate(old_cert.cert_pem.encode())
    public_key_pem = old_x509.public_key().public_bytes(
        encoding=crypto_serialization.Encoding.PEM,
        format=crypto_serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    # 使用旧证书的密钥签发新根证书
    new_serial = generate_serial_number()
    new_cert_pem = build_self_signed_root_cert(
        subject_dn=old_cert.subject_dn,
        public_key_pem=public_key_pem,
        private_key_pem=old_cert.key_pem,
        validity_days=payload.validity_days,
        serial_number=new_serial,
        signature_algorithm=old_cert.signature_algorithm,
    )

    now = datetime.now(timezone.utc)

    new_root = RootCert(
        serial_number=new_serial,
        subject_dn=old_cert.subject_dn,
        issuer_dn=old_cert.subject_dn,
        signature_algorithm=old_cert.signature_algorithm,
        not_before=now,
        not_after=now + timedelta(days=payload.validity_days),
        cert_pem=new_cert_pem,
        key_pem=old_cert.key_pem,
        key_size=old_cert.key_size,
        status="active",
    )
    db.add(new_root)
    await db.flush()

    cert_path = save_keystore_file(f"root_{new_serial}.pem", new_cert_pem)
    key_path = save_keystore_file(f"root_{new_serial}.key", old_cert.key_pem)

    # 更新 CA 配置中的密钥库路径
    ca_stmt = select(CAConfig).where(CAConfig.is_initialized.is_(True))
    ca_result = await db.execute(ca_stmt)
    ca_config = ca_result.scalars().first()
    if ca_config:
        ca_config.keystore_path = cert_path + "\n" + key_path

    import logging
    logger = logging.getLogger(__name__)
    logger.info("管理员 %s 续期了根证书 %s → %s（%s 天）", current_user.username, serial_number, new_serial, payload.validity_days)

    return RootCertRenewResponse(
        success=True,
        message=f"根证书续期成功",
        old_serial_number=serial_number,
        new_serial_number=new_serial,
        subject_dn=old_cert.subject_dn,
        cert_pem=new_cert_pem,
    )
