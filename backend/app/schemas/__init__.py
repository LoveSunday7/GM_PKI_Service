"""按业务域分组的 Pydantic 数据模型."""

from app.schemas.auth import LoginRequest, LoginResponse, LogoutResponse
from app.schemas.ca import (
    CAInitRequest,
    CAInitResponse,
    CAStatusResponse,
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
from app.schemas.system import (
    KeystoreFileItem,
    KeystoreInfoResponse,
    LogLevelRequest,
    LogLevelResponse,
    SystemConfigResponse,
)
from app.schemas.ocsp import OCSPQueryRequest, OCSPQueryResponse
from app.schemas.verify import (
    CertVerifyRequest,
    CertVerifyResponse,
    CRLVerifyRequest,
    CRLVerifyResponse,
)

__all__ = [
    # 认证
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    # 通用
    "SuccessResponse",
    "ErrorResponse",
    # 系统
    "SystemConfigResponse",
    "LogLevelRequest",
    "LogLevelResponse",
    "KeystoreFileItem",
    "KeystoreInfoResponse",
    # CA
    "CAInitRequest",
    "CAInitResponse",
    "CAStatusResponse",
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
    # OCSP
    "OCSPQueryRequest",
    "OCSPQueryResponse",
    # 验证
    "CertVerifyRequest",
    "CertVerifyResponse",
    "CRLVerifyRequest",
    "CRLVerifyResponse",
]
