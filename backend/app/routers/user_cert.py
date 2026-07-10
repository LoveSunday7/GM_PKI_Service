"""用户证书管理接口 — 签发、列表、详情、下载、状态查询、证书申请审核."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ca_config import CAConfig
from app.models.cert_application import CertApplication
from app.models.crl import CRLRevocation
from app.models.root_cert import RootCert
from app.models.user_cert import UserCert
from app.routers.auth import CurrentUser, get_current_user, require_admin
from app.schemas.cert import (
    CertApplicationItem,
    CertApplicationListResponse,
    CertApplyRequest,
    CertApplyResponse,
    CertApproveRequest,
    CertChainNode,
    CertChainResponse,
    CertDetailResponse,
    CertDownloadResponse,
    CertIssueRequest,
    CertIssueResponse,
    CertIssuerItem,
    CertListItem,
    CertListResponse,
    CertRejectRequest,
    CertReviewResponse,
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
    normalize_encryption_algorithm,
    normalize_signature_algorithm,
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


async def _get_issuer_cert(db: AsyncSession, issuer_cert_serial: str | None) -> tuple[str, str, str, str, str]:
    """返回 (issuer_serial, root_serial, subject_dn, cert_pem, key_pem)."""
    if issuer_cert_serial:
        root_stmt = select(RootCert).where(RootCert.serial_number == issuer_cert_serial)
        root_result = await db.execute(root_stmt)
        root = root_result.scalars().first()
        if root:
            return root.serial_number, root.serial_number, root.subject_dn, root.cert_pem, root.key_pem

        stmt = select(UserCert).where(UserCert.serial_number == issuer_cert_serial)
        result = await db.execute(stmt)
        issuer = result.scalars().first()
        if issuer is None:
            raise HTTPException(status_code=404, detail="中间 CA 证书未找到")
        if issuer.cert_type != "intermediate_ca" or not issuer.key_pem:
            raise HTTPException(status_code=400, detail="指定证书不是可签发的中间 CA")
        return issuer.serial_number, issuer.root_cert_serial, issuer.subject_dn, issuer.cert_pem, issuer.key_pem

    root = await _get_active_root_cert(db)
    return root.serial_number, root.serial_number, root.subject_dn, root.cert_pem, root.key_pem


def _build_cert(
    user_name: str,
    organization: str | None,
    department: str | None,
    province: str | None,
    city: str | None,
    email: str | None,
    cert_type: str,
    validity_days: int,
    public_key_pem: str | None,
    issuer_cert_pem: str,
    issuer_key_pem: str,
    issuer_dn: str,
    signature_algorithm: str,
) -> dict:
    """签发单张用户证书，返回 cert dict."""
    if public_key_pem:
        public_pem = public_key_pem
        private_pem = None
    else:
        public_pem, private_pem, _ = generate_sm2_keypair()

    serial = generate_serial_number()
    subject_dn = build_dn(
        common_name=user_name,
        organization=organization or "Default Org",
        country="CN",
        province=province,
        city=city,
    )

    cert_pem = build_user_cert(
        subject_dn=subject_dn,
        public_key_pem=public_pem,
        issuer_cert_pem=issuer_cert_pem,
        issuer_key_pem=issuer_key_pem,
        cert_type=cert_type,
        validity_days=validity_days,
        serial_number=serial,
        signature_algorithm=signature_algorithm,
    )

    return {
        "serial": serial,
        "subject_dn": subject_dn,
        "issuer_dn": issuer_dn,
        "cert_pem": cert_pem,
        "public_key_pem": public_pem,
        "key_pem": private_pem,
    }


async def _find_issuer_pem_for_cert(cert_pem: str, db: AsyncSession) -> str | None:
    """根据证书 issuer DN 在库内寻找上级证书 PEM."""
    from cryptography import x509

    cert = x509.load_pem_x509_certificate(cert_pem.encode())

    root_result = await db.execute(select(RootCert))
    for root in root_result.scalars().all():
        try:
            if x509.load_pem_x509_certificate(root.cert_pem.encode()).subject == cert.issuer:
                return root.cert_pem
        except Exception:
            continue

    user_result = await db.execute(select(UserCert))
    for issuer in user_result.scalars().all():
        try:
            if x509.load_pem_x509_certificate(issuer.cert_pem.encode()).subject == cert.issuer:
                return issuer.cert_pem
        except Exception:
            continue
    return None


async def _build_chain_response(user_cert: UserCert, db: AsyncSession) -> CertChainResponse:
    """按 issuer_cert_serial 向上追溯，返回根/中间 CA/用户证书链."""
    nodes: list[CertChainNode] = []
    current: UserCert | None = user_cert
    seen: set[str] = set()

    while current and current.serial_number not in seen:
        seen.add(current.serial_number)
        nodes.append(CertChainNode(
            serial_number=current.serial_number,
            subject_dn=current.subject_dn,
            issuer_dn=current.issuer_dn,
            cert_type=current.cert_type,
            not_before=current.not_before,
            not_after=current.not_after,
            status=current.status,
            cert_pem=current.cert_pem,
        ))
        parent_serial = current.issuer_cert_serial
        if not parent_serial or parent_serial == current.root_cert_serial:
            break
        parent_result = await db.execute(select(UserCert).where(UserCert.serial_number == parent_serial))
        current = parent_result.scalars().first()

    root_stmt = select(RootCert).where(RootCert.serial_number == user_cert.root_cert_serial)
    root_result = await db.execute(root_stmt)
    root_cert = root_result.scalars().first()
    if root_cert:
        nodes.append(CertChainNode(
            serial_number=root_cert.serial_number,
            subject_dn=root_cert.subject_dn,
            issuer_dn=root_cert.issuer_dn,
            cert_type="root",
            not_before=root_cert.not_before,
            not_after=root_cert.not_after,
            status=root_cert.status,
            cert_pem=root_cert.cert_pem,
        ))

    nodes.reverse()
    verified = True
    for issuer, cert in zip(nodes, nodes[1:]):
        result = verify_cert_chain(cert.cert_pem, issuer.cert_pem)
        verified = verified and bool(result.get("valid"))
    return CertChainResponse(chain=nodes, depth=len(nodes), verified=verified)


@router.post("/issue", response_model=CertIssueResponse)
async def issue_cert(payload: CertIssueRequest, db: AsyncSession = Depends(get_db), current_user: CurrentUser = Depends(require_admin)) -> CertIssueResponse:
    """管理员签发证书：默认签名+加密双证书，也支持签发中间 CA."""
    try:
        signature_algorithm = normalize_signature_algorithm(payload.signature_algorithm)
        encryption_algorithm = normalize_encryption_algorithm(payload.encryption_algorithm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    issuer_serial, root_serial, issuer_dn, issuer_cert_pem, issuer_key_pem = await _get_issuer_cert(db, payload.issuer_cert_serial)
    now = datetime.now(timezone.utc)

    cert_types: list[str] = ["intermediate_ca"] if payload.cert_type == "intermediate_ca" else ["sign", "encrypt"]

    results: dict[str, dict] = {}

    for ct in cert_types:
        info = _build_cert(
            user_name=payload.user_name,
            organization=payload.organization,
            department=payload.department,
            province=payload.province,
            city=payload.city,
            email=payload.email,
            cert_type=ct,
            validity_days=payload.validity_days,
            public_key_pem=payload.public_key_pem if ct == "sign" else None,
            issuer_cert_pem=issuer_cert_pem,
            issuer_key_pem=issuer_key_pem,
            issuer_dn=issuer_dn,
            signature_algorithm=signature_algorithm,
        )
        results[ct] = info

        user_cert = UserCert(
            serial_number=info["serial"],
            cert_type=ct,
            subject_dn=info["subject_dn"],
            issuer_dn=issuer_dn,
            root_cert_serial=root_serial,
            issuer_cert_serial=issuer_serial,
            owner_username=payload.user_name if payload.cert_type != "intermediate_ca" else current_user.username,
            user_name=payload.user_name,
            email=payload.email,
            organization=payload.organization,
            department=payload.department,
            province=payload.province,
            city=payload.city,
            signature_algorithm=signature_algorithm,
            encryption_algorithm=encryption_algorithm,
            not_before=now,
            not_after=now + timedelta(days=payload.validity_days),
            cert_pem=info["cert_pem"],
            key_pem=info["key_pem"],
            public_key_pem=info["public_key_pem"],
            status="active",
        )
        db.add(user_cert)

    await db.flush()

    sign = results.get("sign", {})
    encrypt = results.get("encrypt", {})
    intermediate = results.get("intermediate_ca", {})

    return CertIssueResponse(
        success=True,
        error_code="SUCCESS",
        message="中间 CA 签发成功" if payload.cert_type == "intermediate_ca" else "用户双证书签发成功（签名+加密）",
        sign_serial_number=sign.get("serial"),
        sign_cert_pem=sign.get("cert_pem"),
        sign_public_key_pem=sign.get("public_key_pem"),
        sign_key_pem=sign.get("key_pem"),
        encrypt_serial_number=encrypt.get("serial") if encrypt else None,
        encrypt_cert_pem=encrypt.get("cert_pem") if encrypt else None,
        encrypt_public_key_pem=encrypt.get("public_key_pem") if encrypt else None,
        encrypt_key_pem=encrypt.get("key_pem") if encrypt else None,
        serial_number=intermediate.get("serial"),
        subject_dn=sign.get("subject_dn") or encrypt.get("subject_dn") or intermediate.get("subject_dn"),
        root_dn=issuer_dn,
        root_cert_pem=issuer_cert_pem,
        issuer_cert_serial=issuer_serial,
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


@router.get("/list", response_model=CertListResponse)
async def list_certs(
    cert_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> CertListResponse:
    """查询用户证书列表，支持分页及按类型、状态筛选."""
    # 构建基础查询
    base_stmt = select(UserCert)
    if not _user.is_admin:
        base_stmt = base_stmt.where(UserCert.owner_username == _user.username)
    if cert_type:
        base_stmt = base_stmt.where(UserCert.cert_type == cert_type)
    if status:
        base_stmt = base_stmt.where(UserCert.status == status)

    # 总数
    count_stmt = select(sqlfunc.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    stmt = base_stmt.order_by(UserCert.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    items = [CertListItem.model_validate(c) for c in result.scalars().all()]

    return CertListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ── 证书验证 ──────────────────────────────────────────────────


@router.post("/verify", response_model=CertVerifyResponse)
async def verify_certificate(
    payload: CertVerifyRequest,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
):
    """验证证书链：支持输入 PEM 或证书序列号；可返回完整证书链."""
    cert_pem = payload.cert_pem
    issuer_cert_pem = payload.issuer_cert_pem
    chain_nodes: list[CertChainNode] = []

    if payload.serial_number:
        stmt = select(UserCert).where(UserCert.serial_number == payload.serial_number)
        if not _user.is_admin:
            stmt = stmt.where(UserCert.owner_username == _user.username)
        result = await db.execute(stmt)
        cert = result.scalars().first()
        if cert is None:
            raise HTTPException(status_code=404, detail="证书未找到")
        cert_pem = cert.cert_pem
        chain = await _build_chain_response(cert, db)
        chain_nodes = chain.chain
        if len(chain.chain) >= 2:
            issuer_cert_pem = chain.chain[-2].cert_pem

    if not cert_pem:
        raise HTTPException(status_code=400, detail="请提供 cert_pem 或 serial_number")
    if not issuer_cert_pem:
        issuer_cert_pem = await _find_issuer_pem_for_cert(cert_pem, db)
    if not issuer_cert_pem:
        raise HTTPException(status_code=400, detail="未找到上级证书，请提供 issuer_cert_pem")

    result = verify_cert_chain(cert_pem, issuer_cert_pem)
    if payload.show_chain:
        result["chain"] = [node.model_dump() for node in chain_nodes]
    return result


@router.post("/verify-revocation", response_model=CRLVerifyResponse)
async def verify_certificate_revocation(payload: CRLVerifyRequest, _user: CurrentUser = Depends(get_current_user)):
    """CRL 撤销验证 — 传入证书 PEM + CRL PEM，验证是否已撤销."""
    return verify_cert_against_crl(payload.cert_pem, payload.crl_pem)


# ── 证书申请审核工作流 (RA) ─────────────────────────────────────


@router.post("/apply", response_model=CertApplyResponse)
async def apply_cert(
    payload: CertApplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CertApplyResponse:
    """B002: 提交证书申请 — 进入待审核池."""
    app = CertApplication(
        user_name=payload.user_name,
        email=payload.email,
        organization=payload.organization,
        department=payload.department,
        province=payload.province,
        city=payload.city,
        cert_type=payload.cert_type,
        validity_days=payload.validity_days,
        public_key_pem=payload.public_key_pem,
        signature_algorithm=payload.signature_algorithm,
        encryption_algorithm=payload.encryption_algorithm,
        issuer_cert_serial=payload.issuer_cert_serial,
        status="pending",
        applied_by=current_user.username,
    )
    db.add(app)
    await db.flush()

    import logging
    logger = logging.getLogger(__name__)
    logger.info("证书申请: %s 提交了 %s 证书申请 (id=%s)", current_user.username, payload.cert_type, app.id)

    return CertApplyResponse(
        success=True,
        message="证书申请已提交，等待管理员审核",
        application_id=app.id,
    )


@router.get("/applications", response_model=CertApplicationListResponse)
async def list_applications(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CertApplicationListResponse:
    """管理员查看全部申请；普通用户只查看自己提交的申请."""
    base_stmt = select(CertApplication)
    if not current_user.is_admin:
        base_stmt = base_stmt.where(CertApplication.applied_by == current_user.username)
    if status:
        base_stmt = base_stmt.where(CertApplication.status == status)

    count_stmt = select(sqlfunc.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * page_size
    stmt = base_stmt.order_by(CertApplication.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    items = [CertApplicationItem.model_validate(a) for a in result.scalars().all()]

    return CertApplicationListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/applications/{app_id}/approve", response_model=CertReviewResponse)
async def approve_application(
    app_id: str,
    payload: CertApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> CertReviewResponse:
    """B004: 管理员审核通过 — 自动触发证书签发."""
    stmt = select(CertApplication).where(CertApplication.id == app_id)
    result = await db.execute(stmt)
    app = result.scalars().first()
    if app is None:
        raise HTTPException(status_code=404, detail="申请未找到")
    if app.status != "pending":
        raise HTTPException(status_code=409, detail=f"申请已被{app.status}，无法重复审核")

    try:
        signature_algorithm = normalize_signature_algorithm(app.signature_algorithm)
        encryption_algorithm = normalize_encryption_algorithm(app.encryption_algorithm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    issuer_serial, root_serial, issuer_dn, issuer_cert_pem, issuer_key_pem = await _get_issuer_cert(db, app.issuer_cert_serial)
    now = datetime.now(timezone.utc)
    issued: dict[str, str] = {}
    for cert_type in ("sign", "encrypt"):
        info = _build_cert(
            user_name=app.user_name,
            organization=app.organization,
            department=app.department,
            province=app.province,
            city=app.city,
            email=app.email,
            cert_type=cert_type,
            validity_days=app.validity_days,
            public_key_pem=app.public_key_pem if cert_type == "sign" else None,
            issuer_cert_pem=issuer_cert_pem,
            issuer_key_pem=issuer_key_pem,
            issuer_dn=issuer_dn,
            signature_algorithm=signature_algorithm,
        )
        db.add(UserCert(
            serial_number=info["serial"],
            cert_type=cert_type,
            subject_dn=info["subject_dn"],
            issuer_dn=issuer_dn,
            root_cert_serial=root_serial,
            issuer_cert_serial=issuer_serial,
            owner_username=app.applied_by,
            user_name=app.user_name,
            email=app.email,
            organization=app.organization,
            department=app.department,
            province=app.province,
            city=app.city,
            signature_algorithm=signature_algorithm,
            encryption_algorithm=encryption_algorithm,
            not_before=now,
            not_after=now + timedelta(days=app.validity_days),
            cert_pem=info["cert_pem"],
            key_pem=info["key_pem"],
            public_key_pem=info["public_key_pem"],
            status="active",
        ))
        issued[cert_type] = info["serial"]

    app.status = "approved"
    app.reviewed_by = current_user.username
    app.issued_cert_serial = issued.get("sign")
    app.issued_encrypt_cert_serial = issued.get("encrypt")
    await db.flush()

    import logging
    logger = logging.getLogger(__name__)
    logger.info("管理员 %s 批准了 %s 的双证书申请 (sign=%s, encrypt=%s)", current_user.username, app.user_name, issued.get("sign"), issued.get("encrypt"))

    return CertReviewResponse(
        success=True,
        message="申请已通过，签名证书和加密证书已签发",
        application_id=app_id,
        issued_cert_serial=issued.get("sign"),
        issued_encrypt_cert_serial=issued.get("encrypt"),
    )


@router.get("/issuers", response_model=list[CertIssuerItem])
async def list_cert_issuers(
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> list[CertIssuerItem]:
    """返回用户申请证书时可选择的签发机构：根 CA + 中间 CA."""
    issuers: list[CertIssuerItem] = []

    root_result = await db.execute(select(RootCert).where(RootCert.status == "active").order_by(RootCert.created_at.desc()))
    for root in root_result.scalars().all():
        issuers.append(CertIssuerItem(
            serial_number=root.serial_number,
            subject_dn=root.subject_dn,
            issuer_type="root",
            display_name=f"根 CA - {root.subject_dn}",
        ))

    intermediate_result = await db.execute(
        select(UserCert)
        .where(UserCert.cert_type == "intermediate_ca", UserCert.status == "active")
        .order_by(UserCert.created_at.desc())
    )
    for ca in intermediate_result.scalars().all():
        issuers.append(CertIssuerItem(
            serial_number=ca.serial_number,
            subject_dn=ca.subject_dn,
            issuer_type="intermediate_ca",
            display_name=f"中间 CA - {ca.subject_dn}",
        ))

    return issuers


@router.post("/applications/{app_id}/reject", response_model=CertReviewResponse)
async def reject_application(
    app_id: str,
    payload: CertRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> CertReviewResponse:
    """B005: 管理员拒绝申请."""
    stmt = select(CertApplication).where(CertApplication.id == app_id)
    result = await db.execute(stmt)
    app = result.scalars().first()
    if app is None:
        raise HTTPException(status_code=404, detail="申请未找到")
    if app.status != "pending":
        raise HTTPException(status_code=409, detail=f"申请已被{app.status}，无法重复审核")

    app.status = "rejected"
    app.reject_reason = payload.reason
    app.reviewed_by = current_user.username
    await db.flush()

    import logging
    logger = logging.getLogger(__name__)
    logger.info("管理员 %s 拒绝了 %s 的证书申请（原因: %s）", current_user.username, app.user_name, payload.reason)

    return CertReviewResponse(
        success=True,
        message=f"申请已拒绝（原因: {payload.reason}）",
        application_id=app_id,
    )



@router.get("/{serial_number}", response_model=CertDetailResponse)
async def get_cert_detail(
    serial_number: str, db: AsyncSession = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
) -> CertDetailResponse:
    """查询用户证书详细信息."""
    stmt = select(UserCert).where(UserCert.serial_number == serial_number)
    if not current_user.is_admin:
        stmt = stmt.where(UserCert.owner_username == current_user.username)
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="证书未找到")
    return CertDetailResponse.model_validate(cert)


@router.get("/{serial_number}/download")
async def download_cert(
    serial_number: str, db: AsyncSession = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
):
    """下载用户证书及 CA 证书链（PEM 文件）."""
    from fastapi.responses import PlainTextResponse

    stmt = select(UserCert).where(UserCert.serial_number == serial_number)
    if not current_user.is_admin:
        stmt = stmt.where(UserCert.owner_username == current_user.username)
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="证书未找到")

    chain = await _build_chain_response(cert, db)
    chain_pem = "\n".join(node.cert_pem for node in reversed(chain.chain))

    return PlainTextResponse(
        content=chain_pem,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": f'attachment; filename="{serial_number}.pem"'},
    )


@router.get("/{serial_number}/status", response_model=CertStatusResponse)
async def check_cert_status(
    serial_number: str, db: AsyncSession = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
) -> CertStatusResponse:
    """查询证书的撤销状态."""
    stmt = select(UserCert).where(UserCert.serial_number == serial_number)
    if not current_user.is_admin:
        stmt = stmt.where(UserCert.owner_username == current_user.username)
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

@router.get("/{serial_number}/chain", response_model=CertChainResponse)
async def get_cert_chain(
    serial_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CertChainResponse:
    """返回结构化证书链（根 CA → 中间 CA → 用户证书，含各节点详情）."""
    stmt = select(UserCert).where(UserCert.serial_number == serial_number)
    if not current_user.is_admin:
        stmt = stmt.where(UserCert.owner_username == current_user.username)
    result = await db.execute(stmt)
    user_cert = result.scalars().first()
    if user_cert is None:
        raise HTTPException(status_code=404, detail="证书未找到")

    return await _build_chain_response(user_cert, db)
