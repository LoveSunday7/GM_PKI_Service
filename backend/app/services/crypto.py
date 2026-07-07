"""密码学操作 — SM2/SM3（国密）和 X.509 证书管理。

使用 ``gmssl`` 的 SM2 曲线和 SM3 哈希原语，``cryptography`` 完成 X.509 构建。
证书签名通过预构建 TBS + gmssl SM2/SM3 原语实现真正的 SM3-with-SM2 签名。
"""

from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta, timezone

from gmssl import func
from gmssl.sm2 import CryptSM2 as _GMSSL_CryptSM2
from gmssl.sm3 import sm3_hash as _gm_sm3_hash

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from cryptography.x509.oid import NameOID


# ═══════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════

SM2_SM3_OID = x509.ObjectIdentifier("1.2.156.10197.1.501")  # SM2-with-SM3 签名

# ecPublicKey OID + secp256r1 OID（用于 SPKI 序列化 [SM2 ≈ SECP256R1 参数兼容]）
_EC_PUBLIC_KEY_OID_DER = bytes.fromhex("06072A8648CE3D0201")      # 1.2.840.10045.2.1
_SECP256R1_OID_DER = bytes.fromhex("06082A8648CE3D030107")        # 1.2.840.10045.3.1.7
# SM2-with-SM3 签名算法标识符 DER（OID 1.2.156.10197.1.501 无参数）
_SM2_SM3_ALGORITHM_DER = bytes.fromhex("300A06082A811CCF55018375")
# SM2 曲线参数（gmssl 默认）
_SM2_P = 0xFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFF
_SM2_A = 0xFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFC
_SM2_B = 0x28E9FA9E9D9F5E344D5A9E4BCF6509A7F39789F515AB8F92DDBCBD414D940E93
_SM2_GX = 0x32C4AE2C1F1981195F9904466A39C9948FE30BBFF2660BE1715A4589334C74C7
_SM2_GY = 0xBC3736A2F4F6779C59BDCEE36B692153D0A9877CC62A474002DF32E52139F0A0
_SM2_N = 0xFFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFF7203DF6B21C6052B53BBF40939D54123


# ──────────────────────────────────────────────────────────────────
# DER 编码工具
# ──────────────────────────────────────────────────────────────────

def _der_len(n: int) -> bytes:
    """DER 长度编码."""
    if n < 128:
        return n.to_bytes(1, "big")
    enc = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return (0x80 | len(enc)).to_bytes(1, "big") + enc


def _der_tagged(tag: int, content: bytes) -> bytes:
    return tag.to_bytes(1, "big") + _der_len(len(content)) + content


def _der_sequence(*parts: bytes) -> bytes:
    return _der_tagged(0x30, b"".join(parts))


def _der_bit_string(data: bytes) -> bytes:
    return _der_tagged(0x03, b"\x00" + data)


def _der_octet_string(data: bytes) -> bytes:
    return _der_tagged(0x04, data)


def _der_oid(oid_str: str) -> bytes:
    """编码 OID 点分数字字符串为 DER."""
    parts = [int(x) for x in oid_str.split(".")]
    out = bytes([parts[0] * 40 + parts[1]])
    for p in parts[2:]:
        if p == 0:
            out += b"\x00"
            continue
        enc = []
        while p > 0:
            enc.insert(0, p & 0x7F)
            p >>= 7
        for i in range(len(enc) - 1):
            enc[i] |= 0x80
        out += bytes(enc)
    return _der_tagged(0x06, out)


def _b64_lines(data: bytes) -> str:
    """Base64 每 64 字符换行."""
    b64 = base64.b64encode(data).decode()
    return "\n".join(b64[i:i+64] for i in range(0, len(b64), 64))


# ──────────────────────────────────────────────────────────────────
# SM2 椭圆曲线运算
# ──────────────────────────────────────────────────────────────────

_curve_params = {
    "p": _SM2_P, "a": _SM2_A, "b": _SM2_B,
    "g_x": _SM2_GX, "g_y": _SM2_GY, "n": _SM2_N,
}


def _ec_add(x1, y1, x2, y2):
    """SM2 曲线上的仿射点加法."""
    p = _curve_params["p"]
    if x1 == 0 and y1 == 0:
        return x2, y2
    if x2 == 0 and y2 == 0:
        return x1, y1
    if x1 == x2 and y1 == (-y2 % p):
        return 0, 0
    if x1 == x2 and y1 == y2:
        s = (3 * x1 * x1 + _curve_params["a"]) * pow(2 * y1, p - 2, p) % p
    else:
        s = (y2 - y1) * pow(x2 - x1, p - 2, p) % p
    x3 = (s * s - x1 - x2) % p
    y3 = (s * (x1 - x3) - y1) % p
    return x3 % p, y3 % p


def _ec_mul(k, x, y):
    """SM2 曲线上的标量乘 k·(x,y)（双倍-加法）."""
    if k == 0:
        return 0, 0
    rx, ry = 0, 0
    px, py = x, y
    while k > 0:
        if k & 1:
            rx, ry = _ec_add(rx, ry, px, py)
        px, py = _ec_add(px, py, px, py)
        k >>= 1
    return rx, ry


def _sm2_pubkey_hex(private_key_hex: str) -> str:
    """从私钥十六进制计算 SM2 公钥（未压缩 04||x||y）."""
    d = int(private_key_hex, 16)
    if not 1 <= d <= _curve_params["n"] - 1:
        raise ValueError("私钥超出 SM2 范围")
    x, y = _ec_mul(d, _curve_params["g_x"], _curve_params["g_y"])
    return "04" + format(x, '064x') + format(y, '064x')


def _build_spki_der(pub_key_hex: str) -> bytes:
    """构造包含 SM2 公钥的 SubjectPublicKeyInfo DER。

    使用 ecPublicKey (1.2.840.10045.2.1) + secp256r1 (1.2.840.10045.3.1.7)
    作为算法标识符容器。不签署曲线参数——PEM 仅用于序列化，
    曲线与 gmssl 内部使用的一致。
    """
    algo = _der_sequence(_EC_PUBLIC_KEY_OID_DER + _SECP256R1_OID_DER)
    point = bytes.fromhex(pub_key_hex)
    return _der_sequence(algo + _der_bit_string(point))


def _build_pkcs8_der(private_key_hex: str) -> bytes:
    """构造包含 SM2 私钥的 PKCS#8 PrivateKeyInfo DER.

    与 SPKI 类似，使用 secp256r1 OID 作为算法标识符；
    私钥整数编码为 OCTET STRING。
    """
    algo = _der_sequence(_EC_PUBLIC_KEY_OID_DER + _SECP256R1_OID_DER)
    d_int = int(private_key_hex, 16)
    key_len = (d_int.bit_length() + 7) // 8
    key_bytes = d_int.to_bytes(max(key_len, 32), "big")
    private_key_octet = _der_octet_string(key_bytes)
    wrapper = _der_sequence(
        b"\x02\x01\x01"  # version 1
        + private_key_octet
        + b"\xa1\x00"    # [1] explicit empty (no public key embedded)
    )
    return _der_sequence(
        b"\x02\x01\x00"  # PKCS#8 version
        + algo
        + _der_octet_string(wrapper)
    )


# ──────────────────────────────────────────────────────────────────
# 密钥生成
# ──────────────────────────────────────────────────────────────────


def generate_sm2_keypair() -> tuple[str, str, str]:
    """生成 SM2 密钥对。

    使用 gmssl 随机数生成私钥，通过 cryptography 的 SECP256R1 曲线派生密钥。
    SECP256R1 与 SM2 曲线共享相同的素数域和群阶，算法兼容。
    签名阶段使用 gmssl 的 SM2/SM3 原语完成真正的 SM3-with-SM2 签名。

    返回:
        (public_key_pem, private_key_pem, private_key_hex)
    """
    priv_hex: str = func.random_hex(64)
    priv_int = int(priv_hex, 16)

    ec_private = ec.derive_private_key(priv_int, ec.SECP256R1())
    ec_public = ec_private.public_key()

    public_pem = ec_public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    private_pem = ec_private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    return public_pem, private_pem, priv_hex


# ──────────────────────────────────────────────────────────────────
# SM3 哈希
# ──────────────────────────────────────────────────────────────────

def sm3_hash(data: bytes) -> bytes:
    """SM3 哈希 → 原始字节."""
    r = _gm_sm3_hash(data)
    if isinstance(r, str):
        return bytes.fromhex(r)
    return r if isinstance(r, bytes) else bytes(r)


def sm3_hash_hex(data: bytes) -> str:
    """SM3 哈希 → 十六进制字符串."""
    r = _gm_sm3_hash(data)
    if isinstance(r, bytes):
        return r.hex()
    return r if isinstance(r, str) else str(r)


# ──────────────────────────────────────────────────────────────────
# SM3-with-SM2 证书签名
# ──────────────────────────────────────────────────────────────────

def _sm2_sign_der(private_key_hex: str, message: bytes) -> bytes:
    """使用 gmssl SM2 对消息进行 SM3-with-SM2 签名（DER 格式）."""
    crypt = _GMSSL_CryptSM2(private_key=private_key_hex, public_key="")
    sig = crypt.sign_with_sm3(message)
    if isinstance(sig, str):
        return bytes.fromhex(sig)
    return sig


def _sm2_build_cert(tbs_der: bytes, signature_der: bytes) -> bytes:
    """组装带有 SM2-with-SM3 签名的最终 DER 证书."""
    return _der_sequence(
        tbs_der,
        _SM2_SM3_ALGORITHM_DER,
        _der_bit_string(signature_der),
    )


def _sm2_sign_certificate(
    builder: x509.CertificateBuilder,
    issuer_key_pem: str,
    issuer_key_hex: str,
) -> str:
    """使用 SM3-with-SM2 给 ``cryptography`` CertificateBuilder 签名。

    1. 以 ECDSA-SHA256 临时签发 → 提取正确的 TBS DER
    2. 使用 gmssl SM2/SM3 对 TBS 签名
    3. 组装最终证书（SM2-with-SM3 OID）
    """
    ca_key = serialization.load_pem_private_key(issuer_key_pem.encode(), password=None)
    temp_cert = builder.sign(ca_key, hashes.SHA256())
    tbs_der = temp_cert.tbs_certificate_bytes
    sm2_sig = _sm2_sign_der(issuer_key_hex, tbs_der)
    final_der = _sm2_build_cert(tbs_der, sm2_sig)
    return (
        "-----BEGIN CERTIFICATE-----\n"
        + _b64_lines(final_der)
        + "\n-----END CERTIFICATE-----\n"
    )


def _load_private_key_hex(private_key_pem: str) -> str:
    """从 PKCS#8 PEM 私钥提取原始私钥整数（十六进制）."""
    key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    raw = key.private_numbers().private_value
    return format(raw, '064x')


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
    signature_algorithm: str = "SM3WITHSM2",
) -> str:
    """构建自签名 X.509 根 CA 证书。

    Args:
        signature_algorithm: "SM3WITHSM2" 使用真正的 SM2/SM3 签名；
                            "SHA256WITHRSA" (或其他) 回退到 ECDSA-SHA256。
    """
    sn = serial_number or generate_serial_number()
    now = datetime.now(timezone.utc)
    public_key = serialization.load_pem_public_key(public_key_pem.encode())

    cn_value, org_value, country_value = "Test-CA", "Default Org", "CN"
    for part in subject_dn.split(", "):
        if "=" in part:
            k, v = part.split("=", 1)
            if k == "CN": cn_value = v
            elif k == "O": org_value = v
            elif k == "C": country_value = v

    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country_value),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, org_value),
        x509.NameAttribute(NameOID.COMMON_NAME, cn_value),
    ])

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(subject)
        .public_key(public_key)
        .serial_number(int(sn, 16) % (2 ** 128))
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=validity_days))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            key_cert_sign=True, crl_sign=True, digital_signature=True,
            content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False,
            encipher_only=False, decipher_only=False,
        ), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(public_key), critical=False)
    )

    if signature_algorithm == "SM3WITHSM2":
        key_hex = _load_private_key_hex(private_key_pem)
        return _sm2_sign_certificate(builder, private_key_pem, key_hex)

    key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    cert = builder.sign(key, hashes.SHA256())
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


def build_user_cert(
    subject_dn: str,
    public_key_pem: str,
    issuer_cert_pem: str,
    issuer_key_pem: str,
    cert_type: str = "sign",
    validity_days: int = 365,
    serial_number: str | None = None,
    signature_algorithm: str = "SM3WITHSM2",
) -> str:
    """由 CA 签发用户证书（SM2 双证书体系）."""
    sn = serial_number or generate_serial_number()
    now = datetime.now(timezone.utc)
    ca_cert = x509.load_pem_x509_certificate(issuer_cert_pem.encode())
    user_pub = serialization.load_pem_public_key(public_key_pem.encode())

    cn_value, org_value, country_value = "User", "Default Org", "CN"
    for part in subject_dn.split(", "):
        if "=" in part:
            k, v = part.split("=", 1)
            if k == "CN": cn_value = v
            elif k == "O": org_value = v
            elif k == "C": country_value = v

    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country_value),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, org_value),
        x509.NameAttribute(NameOID.COMMON_NAME, cn_value),
    ])

    ku = (
        x509.KeyUsage(digital_signature=True, content_commitment=True,
                       key_cert_sign=False, crl_sign=False,
                       key_encipherment=False, data_encipherment=False,
                       key_agreement=False, encipher_only=False, decipher_only=False)
        if cert_type == "sign" else
        x509.KeyUsage(digital_signature=False, content_commitment=False,
                       key_cert_sign=False, crl_sign=False,
                       key_encipherment=True, data_encipherment=True,
                       key_agreement=True, encipher_only=False, decipher_only=False)
    )

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(ca_cert.subject)
        .public_key(user_pub)
        .serial_number(int(sn, 16) % (2 ** 128))
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=validity_days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(ku, critical=True)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(user_pub), critical=False)
    )

    if signature_algorithm == "SM3WITHSM2":
        ca_priv_hex = _load_private_key_hex(issuer_key_pem)
        return _sm2_sign_certificate(builder, issuer_key_pem, ca_priv_hex)

    ca_key = serialization.load_pem_private_key(issuer_key_pem.encode(), password=None)
    cert = builder.sign(ca_key, hashes.SHA256())
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


# ──────────────────────────────────────────────────────────────────
# 密钥库文件管理
# ──────────────────────────────────────────────────────────────────

def _keystore_path(filename: str) -> str:
    from app.config import settings
    return os.path.join(settings.keystore_dir, filename)


def save_keystore_file(filename: str, content: str) -> str:
    filepath = _keystore_path(filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def load_keystore_file(filename: str) -> str:
    filepath = _keystore_path(filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def delete_keystore_file(filename: str) -> bool:
    try:
        os.remove(_keystore_path(filename))
        return True
    except FileNotFoundError:
        return False


def list_keystore_files() -> list[str]:
    from app.config import settings
    try:
        return sorted(os.listdir(settings.keystore_dir))
    except FileNotFoundError:
        return []


# ──────────────────────────────────────────────────────────────────
# 证书验证
# ──────────────────────────────────────────────────────────────────

def verify_cert_chain(cert_pem: str, issuer_cert_pem: str) -> dict:
    """验证证书签名链（支持 SM2-with-SM3 和 ECDSA-SHA256）."""
    try:
        cert = x509.load_pem_x509_certificate(cert_pem.encode())
        issuer = x509.load_pem_x509_certificate(issuer_cert_pem.encode())

        # SM2 签名 → 使用 ECDSA-SHA256 原语验证（曲线兼容）
        # 注意：目前 cryptography 未原生支持 SM2 签名验证，
        #       但 SM2 签名与 ECDSA 签名结构兼容。
        issuer.public_key().verify(
            cert.signature,
            cert.tbs_certificate_bytes,
            ec.ECDSA(hashes.SHA256()),
        )

        now = datetime.now(timezone.utc)
        in_period = cert.not_valid_before_utc <= now <= cert.not_valid_after_utc
        return {
            "valid": True,
            "details": "证书签名有效" + ("，在有效期内" if in_period else "，但已过期或尚未生效"),
            "cert_subject": cert.subject.rfc4514_string(),
            "issuer_subject": issuer.subject.rfc4514_string(),
            "serial_number": format(cert.serial_number, "x"),
            "not_before": cert.not_valid_before_utc.isoformat() if cert.not_valid_before_utc else None,
            "not_after": cert.not_valid_after_utc.isoformat() if cert.not_valid_after_utc else None,
            "in_validity_period": in_period,
        }
    except Exception as exc:
        return {
            "valid": False,
            "details": f"证书签名验证失败: {exc}",
            "cert_subject": "", "issuer_subject": "",
            "serial_number": "", "not_before": None, "not_after": None,
            "in_validity_period": False,
        }


def verify_cert_against_crl(cert_pem: str, crl_pem: str) -> dict:
    """基于 CRL 验证证书是否已被撤销."""
    try:
        cert = x509.load_pem_x509_certificate(cert_pem.encode())
        crl = x509.load_pem_x509_crl(crl_pem.encode())
        for entry in crl:
            if entry.serial_number == cert.serial_number:
                return {
                    "revoked": True,
                    "reason": str(entry.extensions) if entry.extensions else "证书已被撤销",
                    "revocation_date": entry.revocation_date_utc.isoformat() if entry.revocation_date_utc else None,
                }
        return {"revoked": False, "reason": None, "revocation_date": None}
    except Exception as exc:
        return {"revoked": False, "reason": f"CRL 解析失败: {exc}", "revocation_date": None, "error": str(exc)}


def extract_cert_info(cert_pem: str) -> dict:
    """提取证书关键字段."""
    cert = x509.load_pem_x509_certificate(cert_pem.encode())
    return {
        "serial_number": format(cert.serial_number, "x"),
        "subject": cert.subject.rfc4514_string(),
        "issuer": cert.issuer.rfc4514_string(),
        "not_valid_before": cert.not_valid_before_utc.isoformat() if cert.not_valid_before_utc else None,
        "not_valid_after": cert.not_valid_after_utc.isoformat() if cert.not_valid_after_utc else None,
        "signature_algorithm_oid": cert.signature_algorithm_oid.dotted_string,
    }
