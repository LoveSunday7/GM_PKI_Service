"""按业务域分组的 Pydantic 数据模型."""

from app.schemas.auth import LoginRequest, LoginResponse, LogoutResponse
from app.schemas.ca import (
    CAInitRequest,
    CAInitResponse,
    RootCertDetailResponse,
    RootCertListItem,
)
from app.schemas.cert import (
    CertDetailResponse,
    CertDownloadResponse,
    CertIssueRequest,
    CertIssueResponse,
    CertListItem,
    CertStatusResponse,
)
from app.schemas.crl import (
    CRLDownloadResponse,
    CRLGenerateResponse,
    CRLQueryResponse,
    CRLRevokeRequest,
    CRLRevokeResponse,
)
from app.schemas.common import ErrorResponse, SuccessResponse

__all__ = [
    # 认证
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    # 通用
    "SuccessResponse",
    "ErrorResponse",
    # CA
    "CAInitRequest",
    "CAInitResponse",
    "RootCertListItem",
    "RootCertDetailResponse",
    # 证书
    "CertIssueRequest",
    "CertIssueResponse",
    "CertListItem",
    "CertDetailResponse",
    "CertDownloadResponse",
    "CertStatusResponse",
    # CRL
    "CRLRevokeRequest",
    "CRLRevokeResponse",
    "CRLGenerateResponse",
    "CRLQueryResponse",
    "CRLDownloadResponse",
]
