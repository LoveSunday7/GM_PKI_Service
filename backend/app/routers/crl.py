"""CRL 管理接口 — 撤销、生成、查询、下载 + 定期自动签发."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.crl import CRLPublish, CRLRevocation
from app.models.revocation_application import RevocationApplication
from app.models.root_cert import RootCert
from app.models.user_cert import UserCert
from app.routers.auth import CurrentUser, get_current_user, require_admin
from app.schemas.crl import (
    CRLDownloadResponse,
    CRLGenerateResponse,
    CRLHistoryItem,
    CRLHistoryResponse,
    CRLQueryResponse,
    CRLRevokeRequest,
    CRLRevokeResponse,
    RevocationApplicationItem,
    RevocationApplicationListResponse,
    RevocationApplyRequest,
    RevocationApplyResponse,
    RevocationReviewRequest,
    RevocationReviewResponse,
)

router = APIRouter(prefix="/api/crl", tags=["CRL"])
logger = logging.getLogger(__name__)


async def _perform_revoke(
    db: AsyncSession,
    cert: UserCert,
    reason: str,
) -> tuple[CRLRevocation, datetime]:
    """执行真实撤销：更新证书状态并写入 CRL 撤销记录."""
    if cert.status in ("revoked", "suspended"):
        raise HTTPException(status_code=409, detail=f"证书已被{cert.status}")

    cert.status = "suspended" if reason == "certificateHold" else "revoked"
    now = datetime.now(timezone.utc)
    rev = CRLRevocation(
        cert_serial_number=cert.serial_number,
        reason=reason,
        revoked_at=now,
    )
    db.add(rev)
    return rev, now

# ── CRL 自动签发后台任务 ──────────────────────────────────────

_auto_task: asyncio.Task[None] | None = None


async def _auto_generate_crl(interval_hours: int) -> None:
    """后台任务：按配置的间隔自动检查新撤销记录并生成 CRL."""
    # 从配置读取间隔（默认 24 小时 → 秒）
    interval_seconds = interval_hours * 3600
    # 但开发/演示环境可能希望更频繁，这里用 10 分钟作为最小检查间隔
    check_interval = min(interval_seconds, 600)  # 每 10 分钟检查一次

    # 启动后等待 30 秒再开始首次检查，避免阻塞启动流程
    await asyncio.sleep(30)

    while True:
        try:
            from app.database import async_session_factory

            async with async_session_factory() as db:
                # 检查是否有未撤销的新记录
                stmt = select(CRLRevocation).limit(1)
                result = await db.execute(stmt)
                if result.scalars().first() is not None:
                    # 检查是否已有CRL包含这些记录（最后一个CRL是否在撤销之后）
                    last_publish = (
                        await db.execute(
                            select(CRLPublish).order_by(CRLPublish.crl_number.desc()).limit(1)
                        )
                    ).scalars().first()

                    if last_publish is None:
                        # 从未生成过CRL，且存在撤销记录 → 生成
                        logger.info("CRL 自动签发：检测到撤销记录，自动生成 CRL")
                        await _do_generate_crl(db)
                    else:
                        # 检查是否有比上次CRL更新的撤销记录
                        latest_rev = (
                            await db.execute(
                                select(CRLRevocation).order_by(CRLRevocation.created_at.desc()).limit(1)
                            )
                        ).scalars().first()
                        if latest_rev and latest_rev.created_at > last_publish.created_at:
                            logger.info("CRL 自动签发：检测到新的撤销记录，自动生成 CRL")
                            await _do_generate_crl(db)
        except Exception:
            logger.exception("CRL 自动签发失败")

        await asyncio.sleep(check_interval)


async def _do_generate_crl(db: AsyncSession) -> None:
    """执行一次 CRL 生成（供自动任务和手动接口共用）."""
    root_stmt = select(RootCert).where(RootCert.status == "active").order_by(RootCert.created_at.desc())
    root_result = await db.execute(root_stmt)
    root_cert = root_result.scalars().first()
    if root_cert is None:
        return

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization

    ca_private_key = serialization.load_pem_private_key(root_cert.key_pem.encode(), password=None)
    ca_cert = x509.load_pem_x509_certificate(root_cert.cert_pem.encode())

    # 校验 cRLSign 权限
    try:
        key_usage_ext = ca_cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.KEY_USAGE)
        if not key_usage_ext.value.crl_sign:
            return
    except x509.extensions.ExtensionNotFound:
        return

    rev_stmt = select(CRLRevocation).order_by(CRLRevocation.revoked_at.asc())
    rev_result = await db.execute(rev_stmt)
    revoked_entries = rev_result.scalars().all()

    if not revoked_entries:
        return

    count_stmt = select(sqlfunc.max(CRLPublish.crl_number))
    count_result = await db.execute(count_stmt)
    last_num = count_result.scalar() or 0
    crl_number = last_num + 1

    now = datetime.now(timezone.utc)
    next_update = now + timedelta(hours=settings.crl_validity_hours)

    crl_entries: list[x509.RevokedCertificate] = []
    for entry in revoked_entries:
        try:
            builder = x509.RevokedCertificateBuilder().serial_number(
                int(entry.cert_serial_number, 16) % (2 ** 128)
            ).revocation_date(entry.revoked_at)
            try:
                from app.schemas.crl import REASON_TO_RFC5280_CODE
                reason_str = getattr(entry, 'reason', 'unspecified') or 'unspecified'
                flag = getattr(x509.ReasonFlags, reason_str, x509.ReasonFlags.unspecified)
                builder = builder.add_extension(x509.CRLReason(flag), critical=False)
            except Exception:
                pass
            revoked_cert = builder.build()
            crl_entries.append(revoked_cert)
        except (ValueError, TypeError):
            continue

    crl_builder = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(ca_cert.subject)
        .last_update(now)
        .next_update(next_update)
        .add_extension(x509.CRLNumber(crl_number), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()),
            critical=False,
        )
    )

    for entry in crl_entries:
        crl_builder = crl_builder.add_revoked_certificate(entry)

    crl = crl_builder.sign(ca_private_key, hashes.SHA256())
    crl_pem = crl.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    # C009: 标记已纳入此 CRL 的撤销记录
    for entry in revoked_entries:
        if entry.first_published_crl is None:
            entry.first_published_crl = crl_number

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
    await db.commit()


def start_auto_crl(interval_hours: int = 24) -> None:
    """启动 CRL 自动签发后台任务."""
    global _auto_task
    if _auto_task is None or _auto_task.done():
        _auto_task = asyncio.create_task(_auto_generate_crl(interval_hours))
        logger.info("CRL 自动签发任务已启动 (检查间隔 %s 小时)", interval_hours)


def stop_auto_crl() -> None:
    """停止 CRL 自动签发后台任务."""
    global _auto_task
    if _auto_task and not _auto_task.done():
        _auto_task.cancel()


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
    payload: CRLRevokeRequest, db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(require_admin)
) -> CRLRevokeResponse:
    """管理员直接撤销证书。

    被撤销的证书将在下次 CRL 生成时体现。
    """
    # 检查证书是否存在
    stmt = select(UserCert).where(UserCert.serial_number == payload.cert_serial_number)
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="证书未找到")

    _, now = await _perform_revoke(db, cert, payload.reason)
    await db.flush()

    return CRLRevokeResponse(
        success=True,
        message="证书撤销成功",
        cert_serial_number=payload.cert_serial_number,
        reason=payload.reason,
        revoked_at=now,
    )


@router.post("/revoke-applications", response_model=RevocationApplyResponse)
async def apply_revocation(
    payload: RevocationApplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RevocationApplyResponse:
    """用户提交证书撤销申请，管理员审核后才真实撤销."""
    stmt = select(UserCert).where(UserCert.serial_number == payload.cert_serial_number)
    if not current_user.is_admin:
        stmt = stmt.where(UserCert.owner_username == current_user.username)
    result = await db.execute(stmt)
    cert = result.scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="证书未找到")
    if cert.status in ("revoked", "suspended"):
        raise HTTPException(status_code=409, detail=f"证书已被{cert.status}")

    pending_stmt = select(RevocationApplication).where(
        RevocationApplication.cert_serial_number == payload.cert_serial_number,
        RevocationApplication.status == "pending",
    )
    pending = (await db.execute(pending_stmt)).scalars().first()
    if pending is not None:
        raise HTTPException(status_code=409, detail="该证书已有待审核的撤销申请")

    app = RevocationApplication(
        cert_serial_number=payload.cert_serial_number,
        reason=payload.reason,
        description=payload.description,
        applied_by=current_user.username,
        status="pending",
    )
    db.add(app)
    await db.flush()
    return RevocationApplyResponse(success=True, message="撤销申请已提交，等待管理员审核", application_id=app.id)


@router.get("/revoke-applications", response_model=RevocationApplicationListResponse)
async def list_revocation_applications(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RevocationApplicationListResponse:
    """管理员查看全部撤销申请；普通用户只查看自己提交的申请."""
    base_stmt = select(RevocationApplication)
    if not current_user.is_admin:
        base_stmt = base_stmt.where(RevocationApplication.applied_by == current_user.username)
    if status:
        base_stmt = base_stmt.where(RevocationApplication.status == status)

    count_stmt = select(sqlfunc.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    offset = (page - 1) * page_size
    stmt = base_stmt.order_by(RevocationApplication.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    items = [RevocationApplicationItem.model_validate(a) for a in result.scalars().all()]
    return RevocationApplicationListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/revoke-applications/{app_id}/approve", response_model=RevocationReviewResponse)
async def approve_revocation_application(
    app_id: str,
    _payload: RevocationReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> RevocationReviewResponse:
    """管理员批准撤销申请，真实撤销证书."""
    stmt = select(RevocationApplication).where(RevocationApplication.id == app_id)
    app = (await db.execute(stmt)).scalars().first()
    if app is None:
        raise HTTPException(status_code=404, detail="撤销申请未找到")
    if app.status != "pending":
        raise HTTPException(status_code=409, detail=f"申请已被{app.status}，无法重复审核")

    cert = (await db.execute(select(UserCert).where(UserCert.serial_number == app.cert_serial_number))).scalars().first()
    if cert is None:
        raise HTTPException(status_code=404, detail="证书未找到")
    await _perform_revoke(db, cert, app.reason)
    app.status = "approved"
    app.reviewed_by = current_user.username
    await db.flush()
    return RevocationReviewResponse(
        success=True,
        message="撤销申请已通过，证书已撤销",
        application_id=app.id,
        cert_serial_number=app.cert_serial_number,
    )


@router.post("/revoke-applications/{app_id}/reject", response_model=RevocationReviewResponse)
async def reject_revocation_application(
    app_id: str,
    payload: RevocationReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
) -> RevocationReviewResponse:
    """管理员拒绝撤销申请."""
    stmt = select(RevocationApplication).where(RevocationApplication.id == app_id)
    app = (await db.execute(stmt)).scalars().first()
    if app is None:
        raise HTTPException(status_code=404, detail="撤销申请未找到")
    if app.status != "pending":
        raise HTTPException(status_code=409, detail=f"申请已被{app.status}，无法重复审核")
    if not payload.reject_reason:
        raise HTTPException(status_code=400, detail="请填写拒绝原因")

    app.status = "rejected"
    app.reject_reason = payload.reject_reason
    app.reviewed_by = current_user.username
    await db.flush()
    return RevocationReviewResponse(
        success=True,
        message=f"撤销申请已拒绝（原因: {payload.reject_reason}）",
        application_id=app.id,
        cert_serial_number=app.cert_serial_number,
    )


@router.post("/generate", response_model=CRLGenerateResponse)
async def generate_crl(db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(require_admin), delta: bool = False) -> CRLGenerateResponse:
    """生成新的 CRL，由根 CA 私钥签名。

    收集所有待处理的撤销记录并签发 CRL。
    delta=true 时生成增量 CRL（仅包含自上一基础 CRL 以来的变更）。
    """
    root_cert = await _get_active_root_cert(db)

    # 加载 CA 密钥与证书
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.x509.oid import CRLEntryExtensionOID, ExtensionOID, ExtensionOID as _ExtOID

    ca_private_key = serialization.load_pem_private_key(root_cert.key_pem.encode(), password=None)
    ca_cert = x509.load_pem_x509_certificate(root_cert.cert_pem.encode())

    # 校验根证书具备 cRLSign 权限
    try:
        key_usage_ext = ca_cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.KEY_USAGE)
        if not key_usage_ext.value.crl_sign:
            raise HTTPException(status_code=400, detail="根证书不具备 CRL 签名权限 (cRLSign)")
    except x509.extensions.ExtensionNotFound:
        raise HTTPException(status_code=400, detail="根证书缺少 KeyUsage 扩展，无法签发 CRL")

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
            builder = x509.RevokedCertificateBuilder().serial_number(
                int(entry.cert_serial_number, 16) % (2**128)
            ).revocation_date(entry.revoked_at)
            try:
                from app.schemas.crl import REASON_TO_RFC5280_CODE
                reason_str = getattr(entry, 'reason', 'unspecified') or 'unspecified'
                flag = getattr(x509.ReasonFlags, reason_str, x509.ReasonFlags.unspecified)
                builder = builder.add_extension(x509.CRLReason(flag), critical=False)
            except Exception:
                pass
            revoked_cert = builder.build()
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

    # C008: Delta CRL — 在添加条目之前附加 DeltaCRLIndicator 扩展
    is_delta = False
    base_crl_number = None
    if delta:
        base_stmt = select(CRLPublish).where(CRLPublish.is_delta == False).order_by(CRLPublish.crl_number.desc()).limit(1)
        base_result = await db.execute(base_stmt)
        base_crl = base_result.scalars().first()
        if base_crl:
            is_delta = True
            base_crl_number = base_crl.crl_number
            crl_builder = crl_builder.add_extension(
                x509.DeltaCRLIndicator(base_crl.crl_number),
                critical=True,
            )

    for entry in crl_entries:
        crl_builder = crl_builder.add_revoked_certificate(entry)

    crl = crl_builder.sign(ca_private_key, hashes.SHA256())
    crl_pem = crl.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    # C009: 标记已纳入此 CRL 的撤销记录
    for entry in revoked_entries:
        if entry.first_published_crl is None:
            entry.first_published_crl = crl_number

    # 持久化 CRL 发布记录
    publish = CRLPublish(
        crl_number=crl_number,
        issuer_dn=root_cert.subject_dn,
        this_update=now,
        next_update=next_update,
        signature_algorithm=root_cert.signature_algorithm,
        crl_pem=crl_pem,
        revoked_count=len(crl_entries),
        is_delta=is_delta,
        base_crl_number=base_crl_number,
    )
    db.add(publish)
    await db.flush()

    msg = f"CRL #{crl_number}{' (增量, 基础 #' + str(base_crl_number) + ')' if is_delta else ''} 已生成，包含 {len(crl_entries)} 个撤销证书"

    return CRLGenerateResponse(
        success=True,
        message=msg,
        crl_number=crl_number,
        this_update=now,
        next_update=next_update,
        revoked_count=len(crl_entries),
        crl_pem=crl_pem,
    )


@router.get("/current", response_model=CRLQueryResponse | dict)
async def get_current_crl(db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)):
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
            "first_published_crl": r.first_published_crl,  # C009
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


@router.get("/download")
async def download_crl(db: AsyncSession = Depends(get_db), _user: CurrentUser = Depends(get_current_user)):
    """下载最新 CRL 文件（PEM 格式）."""
    from fastapi.responses import PlainTextResponse

    stmt = select(CRLPublish).order_by(CRLPublish.crl_number.desc()).limit(1)
    result = await db.execute(stmt)
    crl = result.scalars().first()
    if crl is None:
        raise HTTPException(status_code=404, detail="暂无 CRL 发布记录")
    return PlainTextResponse(
        content=crl.crl_pem,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": f'attachment; filename="crl_{crl.crl_number}.crl"'},
    )


# ── C004: 公开 CRL 端点（无需认证，供 CRL 分发点使用）─────────

@router.get("/public/current", response_model=CRLQueryResponse | dict)
async def get_current_crl_public(db: AsyncSession = Depends(get_db)):
    """公开查询当前 CRL — 无需认证（C004）."""
    stmt = select(CRLPublish).order_by(CRLPublish.crl_number.desc()).limit(1)
    result = await db.execute(stmt)
    crl = result.scalars().first()
    if crl is None:
        return {"message": "暂无 CRL 发布记录", "crl_number": 0, "revoked_count": 0}

    rev_stmt = select(CRLRevocation).order_by(CRLRevocation.revoked_at.desc())
    rev_result = await db.execute(rev_stmt)
    revs = rev_result.scalars().all()

    revoked_list = [
        {
            "cert_serial_number": r.cert_serial_number,
            "reason": r.reason,
            "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
            "first_published_crl": r.first_published_crl,  # C009
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


@router.get("/public/download")
async def download_crl_public(db: AsyncSession = Depends(get_db)):
    """公开下载 CRL — 无需认证（C004）（PEM 格式）."""
    from fastapi.responses import PlainTextResponse

    stmt = select(CRLPublish).order_by(CRLPublish.crl_number.desc()).limit(1)
    result = await db.execute(stmt)
    crl = result.scalars().first()
    if crl is None:
        raise HTTPException(status_code=404, detail="暂无 CRL 发布记录")
    return PlainTextResponse(
        content=crl.crl_pem,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": f'attachment; filename="crl_{crl.crl_number}.crl"'},
    )


@router.get("/history", response_model=CRLHistoryResponse)
async def get_crl_history(
    page: int = 1,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_admin),
) -> CRLHistoryResponse:
    """返回 CRL 发布历史列表，支持分页（需登录）."""
    # 总数
    count_stmt = select(sqlfunc.count(CRLPublish.id))
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    stmt = (
        select(CRLPublish)
        .order_by(CRLPublish.crl_number.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    items = [CRLHistoryItem.model_validate(r) for r in result.scalars().all()]

    return CRLHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
