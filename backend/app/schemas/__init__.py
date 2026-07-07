"""按业务域分组的 Pydantic 数据模型."""

from app.schemas.admin import AdminUserListItem, ChangePasswordRequest, ChangePasswordResponse, CreateAdminUserRequest, CreateAdminUserResponse, DeleteAdminUserResponse
from app.schemas.auth import LoginRequest, LoginResponse, LogoutResponse
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
    CertListItem,
    CertListResponse,
    CertRejectRequest,
    CertReviewResponse,
    CertStatusResponse,
)
from app.schemas.crl import (
    CRLDownloadResponse,
    CRLGenerateResponse,
    CRLHistoryItem,
    CRLHistoryResponse,
    CRLQueryResponse,
    CRLRevokeRequest,
    CRLRevokeResponse,
)
from app.schemas.common import ErrorResponse, SuccessResponse
from app.schemas.system import (
    ConfigUpdateRequest,
    ConfigUpdateResponse,
    DatabaseInfoResponse,
    DatabaseTableInfo,
    KeystoreFileItem,
    KeystoreInfoResponse,
    LogLevelRequest,
    LogLevelResponse,
    LogQueryResponse,
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
    # 管理员
    "CreateAdminUserRequest",
    "CreateAdminUserResponse",
    "AdminUserListItem",
    "DeleteAdminUserResponse",
    "ChangePasswordRequest",
    "ChangePasswordResponse",
    # 通用
    "SuccessResponse",
    "ErrorResponse",
    # 系统
    "SystemConfigResponse",
    "LogLevelRequest",
    "LogLevelResponse",
    "KeystoreFileItem",
    "KeystoreInfoResponse",
    "ConfigUpdateRequest",
    "ConfigUpdateResponse",
    "DatabaseInfoResponse",
    "DatabaseTableInfo",
    "LogQueryResponse",
    # CA
    "CAInitRequest",
    "CAInitResponse",
    "CAStatusResponse",
    "RootCertListItem",
    "RootCertDetailResponse",
    "RootCertRevokeRequest",
    "RootCertRevokeResponse",
    "RootCertRenewRequest",
    "RootCertRenewResponse",
    # 证书
    "CertIssueRequest",
    "CertIssueResponse",
    "CertListItem",
    "CertListResponse",
    "CertDetailResponse",
    "CertDownloadResponse",
    "CertStatusResponse",
    "CertApplyRequest",
    "CertApplyResponse",
    "CertApplicationItem",
    "CertApplicationListResponse",
    "CertApproveRequest",
    "CertRejectRequest",
    "CertReviewResponse",
    "CertChainNode",
    "CertChainResponse",
    # CRL
    "CRLRevokeRequest",
    "CRLRevokeResponse",
    "CRLGenerateResponse",
    "CRLQueryResponse",
    "CRLDownloadResponse",
    "CRLHistoryItem",
    "CRLHistoryResponse",
    # OCSP
    "OCSPQueryRequest",
    "OCSPQueryResponse",
    # 验证
    "CertVerifyRequest",
    "CertVerifyResponse",
    "CRLVerifyRequest",
    "CRLVerifyResponse",
]
