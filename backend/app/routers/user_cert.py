"""用户证书管理接口 — 签发、列表、详情、下载、状态查询."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ca_config import CAConfig
from app.models.crl import CRLRevocation
from app.models.root_cert import RootCert
from app.models.user_cert import UserCert
from app.routers.auth import CurrentUser, get_current_user
from app.schemas.cert import (
    CertDetailResponse,
    CertDownloadResponse,
    CertIssueRequest,
    CertIssueResponse,
    CertListItem,
    CertStatusResponse,
)
from app.schemas.verify import (
    CertVerifyRequest,
    CertVerifyResponse,
    CRLVerifyRequest,
    CRLVerifyResponse,
)
from app.services.crypto import (
    build_dn,
    build_user_cert,
    generate_serial_number,
    generate_sm2_keypair,
    verify_cert_chain,
    verify_cert_against_crl,
)

router = APIRouter(prefix="/api/cert", tags=["用户证书"])


async def _get_active_root_cert(db: AsyncSession) -> RootCert:
    """辅助函数：获取当前有效的根证书，否则抛出异常."""
    stmt = select(RootCert).where(RootCert.status == "active").order_by(RootCert.created_at.desc())
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=400, detail="没有可用的根证书，请先初始化 CA。")
    return cert


@router.post("/issue", response_model=CertIssueResponse)
async def issue_cert(payload: CertIssueRequest, db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)) -> CertIssueResponse:
    """签发新的用户证书（签名证书或加密证书）。"""
    root_cert = await _get_active_root_cert(db)

    # 生成或导入密钥对
    if payload.public_key_pem:
        public_pem = payload.public_key_pem
        private_pem = None
    else:
        public_pem, private_pem, _ = generate_sm2_keypair()

    serial = generate_serial_number()

    # 构建用户主题 DN
    subject_dn = build_dn(
        common_name=payload.user_name,
        organization=payload.organization or "Default Org",
        country="CN",
        province=payload.province,
        city=payload.city,
    )

    # 由 CA 签发用户证书
    cert_pem = build_user_cert(
        subject_dn=subject_dn,
        public_key_pem=public_pem,
        issuer_cert_pem=root_cert.cert_pem,
        issuer_key_pem=root_cert.key_pem,
        cert_type=payload.cert_type,
        validity_days=payload.validity_days,
        serial_number=serial,
    )

    now = datetime.now(timezone.utc)

    user_cert = UserCert(
        serial_number=serial,
        cert_type=payload.cert_type,
        subject_dn=subject_dn,
        issuer_dn=root_cert.subject_dn,
        root_cert_serial=root_cert.serial_number,
        user_name=payload.user_name,
        email=payload.email,
        organization=payload.organization,
        department=payload.department,
        province=payload.province,
        city=payload.city,
        signature_algorithm=root_cert.signature_algorithm,
        not_before=now,
        not_after=now.replace(year=now.year + (payload.validity_days // 365)),
        cert_pem=cert_pem,
        key_pem=private_pem,
        public_key_pem=public_pem,
        status="active",
    )
    db.add(user_cert)
    await db.flush()

    return CertIssueResponse(
        success=True,
        message="用户证书签发成功",
        serial_number=serial,
        subject_dn=subject_dn,
        cert_pem=cert_pem,
        public_key_pem=public_pem,
        key_pem=private_pem,
        root_cert_pem=root_cert.cert_pem,
    )


@router.get("/stats")
async def cert_stats(db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)):
    """仪表盘统计数据."""
    total_stmt = select(sqlfunc.count(UserCert.id))
    total = (await db.execute(total_stmt)).scalar() or 0
    active_stmt = select(sqlfunc.count(UserCert.id)).where(UserCert.status == "active")
    active = (await db.execute(active_stmt)).scalar() or 0
    revoked_stmt = select(sqlfunc.count(UserCert.id)).where(UserCert.status == "revoked")
    revoked = (await db.execute(revoked_stmt)).scalar() or 0
    sign_stmt = select(sqlfunc.count(UserCert.id)).where(UserCert.cert_type == "sign")
    sign = (await db.execute(sign_stmt)).scalar() or 0
    encrypt_stmt = select(sqlfunc.count(UserCert.id)).where(UserCert.cert_type == "encrypt")
    encrypt = (await db.execute(encrypt_stmt)).scalar() or 0

    from datetime import datetime as dt, timedelta, timezone as tz
    threshold = dt.now(tz.utc) + timedelta(days=30)
    expiring_stmt = select(sqlfunc.count(UserCert.id)).where(
        UserCert.status == "active", UserCert.not_after <= threshold
    )
    expiring = (await db.execute(expiring_stmt)).scalar() or 0

    today_start = dt.now(tz.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_issued_stmt = select(sqlfunc.count(UserCert.id)).where(UserCert.created_at >= today_start)
    today_issued = (await db.execute(today_issued_stmt)).scalar() or 0

    return {
        "total": total, "active": active, "revoked": revoked,
        "sign": sign, "encrypt": encrypt, "expiring_soon": expiring,
        "today_issued": today_issued,
    }


@router.get("/activity")
async def recent_activity(db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)):
    """返回最近 10 条操作时间线（证书签发、撤销、CRL 发布）."""
    activities: list[dict] = []

    # 最近签发的证书
    issued = (await db.execute(
        select(UserCert).order_by(UserCert.created_at.desc()).limit(10)
    )).scalars().all()
    for c in issued:
        activities.append({
            "type": "issue",
            "time": c.created_at.isoformat(),
            "user": c.user_name,
            "serial": c.serial_number[:16],
            "detail": f"签发 {c.cert_type} 证书给 {c.user_name}",
        })

    # 最近撤销
    revocations = (await db.execute(
        select(CRLRevocation).order_by(CRLRevocation.revoked_at.desc()).limit(10)
    )).scalars().all()
    for r in revocations:
        activities.append({
            "type": "revoke",
            "time": r.revoked_at.isoformat() if r.revoked_at else r.created_at.isoformat(),
            "user": r.cert_serial_number[:16],
            "serial": r.cert_serial_number[:16],
            "detail": f"撤销证书 {r.cert_serial_number[:16]}... ({r.reason})",
        })

    # 最近 CRL 发布
    from app.models.crl import CRLPublish
    publishes = (await db.execute(
        select(CRLPublish).order_by(CRLPublish.created_at.desc()).limit(10)
    )).scalars().all()
    for p in publishes:
        activities.append({
            "type": "crl",
            "time": p.created_at.isoformat(),
            "user": f"CRL #{p.crl_number}",
            "serial": f"CRL#{p.crl_number}",
            "detail": f"生成 CRL #{p.crl_number}（撤销 {p.revoked_count} 张证书）",
        })

    # 按时间降序，取前 10
    activities.sort(key=lambda a: a["time"], reverse=True)

    return {"activities": activities[:10]}


@router.get("/list", response_model=list[CertListItem])
async def list_certs(
    cert_type: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> list[CertListItem]:
    """查询用户证书列表，可按类型和状态筛选."""
    stmt = select(UserCert)
    if cert_type:
        stmt = stmt.where(UserCert.cert_type == cert_type)
    if status:
        stmt = stmt.where(UserCert.status == status)
    stmt = stmt.order_by(UserCert.created_at.desc())
    result = await db.execute(stmt)
    certs = result.scalars().all()
    return [CertListItem.model_validate(c) for c in certs]


@router.get("/{serial_number}", response_model=CertDetailResponse)
async def get_cert_detail(
    serial_number: str, db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)
) -> CertDetailResponse:
    """查询用户证书详细信息."""
    stmt = select(UserCert).where(UserCert.serial_number == serial_number)
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="证书未找到")
    return CertDetailResponse.model_validate(cert)


@router.get("/{serial_number}/download", response_model=CertDownloadResponse)
async def download_cert(
    serial_number: str, db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)
) -> CertDownloadResponse:
    """下载用户证书（PEM）及 CA 证书链."""
    stmt = select(UserCert).where(UserCert.serial_number == serial_number)
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="证书未找到")

    # 同时获取根证书以组成证书链
    root_stmt = select(RootCert).where(RootCert.serial_number == cert.root_cert_serial)
    root_result = await db.execute(root_stmt)
    root_cert = root_result.scalars().first()

    return CertDownloadResponse(
        cert_pem=cert.cert_pem,
        key_pem=cert.key_pem,
        root_cert_pem=root_cert.cert_pem if root_cert else None,
        filename=f"{serial_number}.pem",
    )


@router.get("/{serial_number}/status", response_model=CertStatusResponse)
async def check_cert_status(
    serial_number: str, db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)
) -> CertStatusResponse:
    """查询证书的撤销状态."""
    stmt = select(UserCert).where(UserCert.serial_number == serial_number)
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="证书未找到")

    response = CertStatusResponse(serial_number=serial_number, status=cert.status)

    if cert.status == "revoked":
        rev_stmt = select(CRLRevocation).where(
            CRLRevocation.cert_serial_number == serial_number
        )
        rev_result = await db.execute(rev_stmt)
        rev = rev_result.scalars().first()
        if rev:
            response.revoked_at = rev.revoked_at
            response.reason = rev.reason

    return response


# ── 证书验证 ──────────────────────────────────────────────────


@router.post("/verify", response_model=CertVerifyResponse)
async def verify_certificate(payload: CertVerifyRequest, _user: CurrentUser = Depends(get_current_user)):
    """验证证书签名链 — 传入证书 + 上级证书，返回验证结果."""
    return verify_cert_chain(payload.cert_pem, payload.issuer_cert_pem)


@router.post("/verify-revocation", response_model=CRLVerifyResponse)
async def verify_certificate_revocation(payload: CRLVerifyRequest, _user: CurrentUser = Depends(get_current_user)):
    """CRL 撤销验证 — 传入证书 PEM + CRL PEM，验证是否已撤销."""
    return verify_cert_against_crl(payload.cert_pem, payload.crl_pem)
