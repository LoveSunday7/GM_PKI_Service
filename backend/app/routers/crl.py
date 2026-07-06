"""CRL 管理接口 — 撤销、生成、查询、下载."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.crl import CRLPublish, CRLRevocation
from app.models.root_cert import RootCert
from app.models.user_cert import UserCert
from app.schemas.crl import (
    CRLDownloadResponse,
    CRLGenerateResponse,
    CRLQueryResponse,
    CRLRevokeRequest,
    CRLRevokeResponse,
)

router = APIRouter(prefix="/api/crl", tags=["CRL"])


async def _get_active_root_cert(db: AsyncSession) -> RootCert:
    """辅助函数：获取当前有效的根证书."""
    stmt = select(RootCert).where(RootCert.status == "active").order_by(RootCert.created_at.desc())
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=400, detail="没有可用的根证书，请先初始化 CA。")
    return cert


@router.post("/revoke", response_model=CRLRevokeResponse)
async def revoke_certificate(
    payload: CRLRevokeRequest, db: AsyncSession = Depends(get_db)
) -> CRLRevokeResponse:
    """登记证书撤销申请。

    被撤销的证书将在下次 CRL 生成时体现。
    """
    # 检查证书是否存在
    stmt = select(UserCert).where(UserCert.serial_number == payload.cert_serial_number)
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="证书未找到")
    if cert.status == "revoked":
        raise HTTPException(status_code=409, detail="证书已被撤销")

    # 标记为已撤销
    cert.status = "revoked"
    now = datetime.now(timezone.utc)

    rev = CRLRevocation(
        cert_serial_number=payload.cert_serial_number,
        reason=payload.reason,
        revoked_at=now,
    )
    db.add(rev)
    await db.flush()

    return CRLRevokeResponse(
        success=True,
        message="证书撤销成功",
        cert_serial_number=payload.cert_serial_number,
        reason=payload.reason,
        revoked_at=now,
    )


@router.post("/generate", response_model=CRLGenerateResponse)
async def generate_crl(db: AsyncSession = Depends(get_db)) -> CRLGenerateResponse:
    """生成新的 CRL，由根 CA 私钥签名。

    收集所有待处理的撤销记录并签发 CRL。
    """
    root_cert = await _get_active_root_cert(db)

    # 加载 CA 密钥
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.x509.oid import CRLEntryExtensionOID, ExtensionOID

    ca_private_key = serialization.load_pem_private_key(root_cert.key_pem.encode(), password=None)
    ca_cert = x509.load_pem_x509_certificate(root_cert.cert_pem.encode())

    # 获取所有已撤销但尚未发布到 CRL 的证书
    rev_stmt = select(CRLRevocation).order_by(CRLRevocation.revoked_at.asc())
    rev_result = await db.execute(rev_stmt)
    revoked_entries = rev_result.scalars().all()

    # 确定下一个 CRL 编号
    count_stmt = select(sqlfunc.max(CRLPublish.crl_number))
    count_result = await db.execute(count_stmt)
    last_num = count_result.scalar() or 0
    crl_number = last_num + 1

    now = datetime.now(timezone.utc)
    next_update = now + timedelta(hours=settings.crl_validity_hours)

    # 构建 CRL 条目
    crl_entries: list[x509.RevokedCertificate] = []
    for entry in revoked_entries:
        try:
            revoked_cert = x509.RevokedCertificateBuilder().serial_number(
                int(entry.cert_serial_number, 16) % (2**128)
            ).revocation_date(entry.revoked_at).build()
            crl_entries.append(revoked_cert)
        except (ValueError, TypeError):
            continue

    # 构建 CRL
    crl_builder = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(ca_cert.subject)
        .last_update(now)
        .next_update(next_update)
        .add_extension(
            x509.CRLNumber(crl_number),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()),
            critical=False,
        )
    )

    for entry in crl_entries:
        crl_builder = crl_builder.add_revoked_certificate(entry)

    crl = crl_builder.sign(ca_private_key, hashes.SHA256())
    crl_pem = crl.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    # 持久化 CRL 发布记录
    publish = CRLPublish(
        crl_number=crl_number,
        issuer_dn=root_cert.subject_dn,
        this_update=now,
        next_update=next_update,
        signature_algorithm=root_cert.signature_algorithm,
        crl_pem=crl_pem,
        revoked_count=len(crl_entries),
    )
    db.add(publish)
    await db.flush()

    return CRLGenerateResponse(
        success=True,
        message=f"CRL #{crl_number} 已生成，包含 {len(crl_entries)} 个撤销证书",
        crl_number=crl_number,
        this_update=now,
        next_update=next_update,
        revoked_count=len(crl_entries),
        crl_pem=crl_pem,
    )


@router.get("/current", response_model=CRLQueryResponse | dict)
async def get_current_crl(db: AsyncSession = Depends(get_db)):
    """查询当前最新的 CRL 及撤销明细."""
    stmt = select(CRLPublish).order_by(CRLPublish.crl_number.desc()).limit(1)
    result = await db.execute(stmt)
    crl = result.scalars().first()
    if crl is None:
        return {"message": "暂无 CRL 发布记录", "crl_number": 0, "revoked_count": 0}

    # 收集撤销明细
    rev_stmt = select(CRLRevocation).order_by(CRLRevocation.revoked_at.desc())
    rev_result = await db.execute(rev_stmt)
    revs = rev_result.scalars().all()

    revoked_list = [
        {
            "cert_serial_number": r.cert_serial_number,
            "reason": r.reason,
            "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
        }
        for r in revs
    ]

    return CRLQueryResponse(
        crl_number=crl.crl_number,
        issuer_dn=crl.issuer_dn,
        this_update=crl.this_update,
        next_update=crl.next_update,
        signature_algorithm=crl.signature_algorithm,
        revoked_count=crl.revoked_count,
        crl_pem=crl.crl_pem,
        revoked_certificates=revoked_list,
        created_at=crl.created_at,
    )


@router.get("/download", response_model=CRLDownloadResponse)
async def download_crl(db: AsyncSession = Depends(get_db)):
    """下载最新 CRL 文件."""
    stmt = select(CRLPublish).order_by(CRLPublish.crl_number.desc()).limit(1)
    result = await db.execute(stmt)
    crl = result.scalars().first()
    if crl is None:
        raise HTTPException(status_code=404, detail="暂无 CRL 发布记录")
    return CRLDownloadResponse(crl_pem=crl.crl_pem, filename=f"crl_{crl.crl_number}.crl")
