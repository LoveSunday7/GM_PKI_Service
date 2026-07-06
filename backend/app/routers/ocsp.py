"""OCSP 在线证书状态查询接口."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth import CurrentUser, get_current_user
from app.schemas.ocsp import OCSPQueryRequest, OCSPQueryResponse
from app.services.ocsp import query_ocsp_status, sign_ocsp_response

router = APIRouter(prefix="/api/ocsp", tags=["OCSP"])


@router.post("/query", response_model=OCSPQueryResponse)
async def ocsp_query(
    payload: OCSPQueryRequest,
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> OCSPQueryResponse:
    """OCSP 实时证书状态查询 — 返回 good / revoked / unknown."""
    result = await query_ocsp_status(db, payload.cert_serial_number)
    result = await sign_ocsp_response(result, db)
    return OCSPQueryResponse(**result)
