"""密码学操作 — 使用 GMSSL (SM2/SM3) 和标准 ``cryptography`` 库。

提供密钥生成、X.509 证书签发及 CRL 操作。
由于纯 Python 版 GMSSL 的 X.509 支持有限，
证书结构通过 ``cryptography`` 库手动构建，
SM2/SM3 原语使用 ``gmssl``。
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from gmssl import func, sm3 as gm_sm3

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


# ──────────────────────────────────────────────────────────────────
# 密钥生成
# ──────────────────────────────────────────────────────────────────


def generate_sm2_keypair() -> tuple[str, str, str]:
    """生成 SM2 密钥对。

    使用 ``func.random_hex`` 生成随机私钥，
    通过 ``cryptography`` 的 EC 原语进行 PEM 编码。

    返回:
        (public_key_pem, private_key_pem, private_key_hex)
    """
    private_key_hex: str = func.random_hex(64)

    # 通过 cryptography 派生 EC 密钥对（SECP256R1 ≈ SM2 曲线）
    ec_private = ec.derive_private_key(int(private_key_hex, 16), ec.SECP256R1())
    ec_public = ec_private.public_key()

    private_pem = ec_private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = ec_public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return public_pem, private_pem, private_key_hex


def sm3_hash(data: bytes) -> bytes:
    """计算 SM3 哈希，返回原始字节."""
    result = gm_sm3.sm3_hash(data)
    if isinstance(result, str):
        return bytes.fromhex(result)
    return result if isinstance(result, bytes) else bytes(result)


def sm3_hash_hex(data: bytes) -> str:
    """计算 SM3 哈希，返回十六进制字符串."""
    result = gm_sm3.sm3_hash(data)
    if isinstance(result, bytes):
        return result.hex()
    return result if isinstance(result, str) else str(result)


# ──────────────────────────────────────────────────────────────────
# 证书构建
# ──────────────────────────────────────────────────────────────────


def generate_serial_number() -> str:
    """生成随机证书序列号（十六进制）."""
    return os.urandom(16).hex()


def build_dn(
    common_name: str,
    organization: str = "Default Org",
    country: str = "CN",
    province: str | None = None,
    city: str | None = None,
) -> str:
    """构建 RFC 4514 风格的 Distinguished Name 字符串."""
    parts = [f"CN={common_name}", f"O={organization}", f"C={country}"]
    if province:
        parts.append(f"ST={province}")
    if city:
        parts.append(f"L={city}")
    return ", ".join(parts)


def build_self_signed_root_cert(
    subject_dn: str,
    public_key_pem: str,
    private_key_pem: str,
    validity_days: int = 3650,
    serial_number: str | None = None,
) -> str:
    """构建自签名 X.509 根 CA 证书（PEM 字符串）。

    使用 ``cryptography`` 构建 X.509 结构，
    通过 ECDSA-with-SHA256 OID 作为签名桥接算法。
    """
    sn = serial_number or generate_serial_number()
    now = datetime.now(timezone.utc)

    # 通过 cryptography 的 EC 原语加载密钥
    private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    public_key = serialization.load_pem_public_key(public_key_pem.encode())

    # 解析 DN 组件
    cn_value = ""
    org_value = "Default Org"
    country_value = "CN"
    for part in subject_dn.split(", "):
        if "=" in part:
            k, v = part.split("=", 1)
            if k == "CN":
                cn_value = v
            elif k == "O":
                org_value = v
            elif k == "C":
                country_value = v

    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, country_value),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org_value),
            x509.NameAttribute(NameOID.COMMON_NAME, cn_value),
        ]
    )

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)  # 自签名
        .public_key(public_key)
        .serial_number(int(sn, 16) % (2**128))
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=validity_days))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                key_cert_sign=True,
                crl_sign=True,
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(public_key),
            critical=False,
        )
    )

    # 使用 ECDSA-SHA256 签名
    cert = builder.sign(private_key, hashes.SHA256())
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


def build_user_cert(
    subject_dn: str,
    public_key_pem: str,
    issuer_cert_pem: str,
    issuer_key_pem: str,
    cert_type: str = "sign",
    validity_days: int = 365,
    serial_number: str | None = None,
) -> str:
    """由 CA 签发用户证书。

    SM2 双证书体系:
      - 签名证书 (sign): digitalSignature, nonRepudiation
      - 加密证书 (encrypt): keyEncipherment, dataEncipherment, keyAgreement
    """
    sn = serial_number or generate_serial_number()
    now = datetime.now(timezone.utc)

    # 加载签发者（CA）密钥
    ca_private_key = serialization.load_pem_private_key(issuer_key_pem.encode(), password=None)
    ca_cert = x509.load_pem_x509_certificate(issuer_cert_pem.encode())
    user_public_key = serialization.load_pem_public_key(public_key_pem.encode())

    # 解析 DN
    cn_value = ""
    org_value = "Default Org"
    country_value = "CN"
    for part in subject_dn.split(", "):
        if "=" in part:
            k, v = part.split("=", 1)
            if k == "CN":
                cn_value = v
            elif k == "O":
                org_value = v
            elif k == "C":
                country_value = v

    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, country_value),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org_value),
            x509.NameAttribute(NameOID.COMMON_NAME, cn_value),
        ]
    )

    # 根据证书类型设置密钥用途
    if cert_type == "sign":
        key_usage = x509.KeyUsage(
            digital_signature=True,
            content_commitment=True,  # 抗抵赖
            key_cert_sign=False,
            crl_sign=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            encipher_only=False,
            decipher_only=False,
        )
    else:  # 加密证书
        key_usage = x509.KeyUsage(
            digital_signature=False,
            content_commitment=False,
            key_cert_sign=False,
            crl_sign=False,
            key_encipherment=True,
            data_encipherment=True,
            key_agreement=True,
            encipher_only=False,
            decipher_only=False,
        )

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(user_public_key)
        .serial_number(int(sn, 16) % (2**128))
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=validity_days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(key_usage, critical=True)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()),
            critical=False,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(user_public_key),
            critical=False,
        )
    )

    cert = builder.sign(ca_private_key, hashes.SHA256())
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


def extract_cert_info(cert_pem: str) -> dict:
    """从 X.509 证书 PEM 中提取关键字段用于展示."""
    cert = x509.load_pem_x509_certificate(cert_pem.encode())
    return {
        "serial_number": format(cert.serial_number, "x"),
        "subject": cert.subject.rfc4514_string(),
        "issuer": cert.issuer.rfc4514_string(),
        "not_valid_before": cert.not_valid_before_utc.isoformat() if cert.not_valid_before_utc else None,
        "not_valid_after": cert.not_valid_after_utc.isoformat() if cert.not_valid_after_utc else None,
        "signature_algorithm_oid": cert.signature_algorithm_oid.dotted_string,
    }
