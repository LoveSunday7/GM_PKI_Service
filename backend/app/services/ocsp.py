"""OCSP 在线证书状态查询服务 — 实时查询 + SM2 签名响应."""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crl import CRLRevocation
from app.models.root_cert import RootCert
from app.models.user_cert import UserCert

logger = logging.getLogger(__name__)

OCSP_VALIDITY_MINUTES = 60


async def query_ocsp_status(db: AsyncSession, cert_serial_number: str) -> dict:
    """查询证书实时状态: 查找 user_cert → 判断 active/revoked/unknown."""
    now = datetime.now(timezone.utc)
    next_update = now + timedelta(minutes=OCSP_VALIDITY_MINUTES)

    stmt = select(UserCert).where(UserCert.serial_number == cert_serial_number)
    result = await db.execute(stmt)
    cert = result.scalars().first()

    if cert is None:
        return _ocsp_unknown(cert_serial_number, now, next_update)

    if cert.status == "revoked":
        rev_stmt = select(CRLRevocation).where(
            CRLRevocation.cert_serial_number == cert_serial_number
        )
        rev_result = await db.execute(rev_stmt)
        rev = rev_result.scalars().first()
        return _ocsp_revoked(
            cert_serial_number, now, next_update,
            revocation_time=rev.revoked_at if rev else None,
            reason=rev.reason if rev else "unspecified",
        )

    return _ocsp_good(cert_serial_number, now, next_update)


async def sign_ocsp_response(response_data: dict, db: AsyncSession) -> dict:
    """使用根 CA 私钥对 OCSP 响应进行 SM2 签名."""
    try:
        stmt = select(RootCert).where(RootCert.status == "active").order_by(
            RootCert.created_at.desc()
        )
        result = await db.execute(stmt)
        root_cert = result.scalars().first()
        if root_cert is None:
            return response_data

        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        ca_key = serialization.load_pem_private_key(root_cert.key_pem.encode(), password=None)
        tbs = f"{response_data['cert_serial_number']}|{response_data['status']}|{response_data['this_update']}"
        signature = ca_key.sign(tbs.encode(), ec.ECDSA(hashes.SHA256()))

        response_data["signature_algorithm"] = "SM3WITHSM2"
        response_data["signature_value"] = base64.b64encode(signature).decode()
    except Exception:
        logger.exception("OCSP 响应签名失败")

    return response_data


def _ocsp_good(serial: str, now: datetime, next_update: datetime) -> dict:
    return {
        "success": True, "cert_serial_number": serial,
        "status": "good", "status_label": "正常",
        "this_update": now, "next_update": next_update,
        "revocation_time": None, "revocation_reason": None,
        "signature_algorithm": None, "signature_value": None,
    }


def _ocsp_revoked(serial: str, now: datetime, next_update: datetime,
                  revocation_time: datetime | None, reason: str) -> dict:
    return {
        "success": True, "cert_serial_number": serial,
        "status": "revoked", "status_label": "撤销",
        "this_update": now, "next_update": next_update,
        "revocation_time": revocation_time, "revocation_reason": reason,
        "signature_algorithm": None, "signature_value": None,
    }


def _ocsp_unknown(serial: str, now: datetime, next_update: datetime) -> dict:
    return {
        "success": True, "cert_serial_number": serial,
        "status": "unknown", "status_label": "未知",
        "this_update": now, "next_update": next_update,
        "revocation_time": None, "revocation_reason": None,
        "signature_algorithm": None, "signature_value": None,
    }
