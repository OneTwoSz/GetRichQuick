"""
Signing service — detached signatures over SHA-256 hashes of canonical JSON.

Two providers:

  * **local** — Ed25519 keypair stored in the FactoryKey table. Fast, zero
    infra, perfect for dev and the SMB tier. Signatures are 64 bytes each
    and there's no per-call cost.

  * **kms** — AWS KMS asymmetric key (ECDSA_SHA_256). The private key never
    leaves KMS; we only store the key ARN. More auditable and rotatable for
    enterprise deployments that demand "the signing key is not on your
    server." Costs ~$0.03 per signature plus $1/month per KMS key.

The caller never needs to know which provider is active. `sign_report()`
takes a Report, loads or creates the factory's active key, computes the
signature, and persists a ReportSignature row.

Verification (`verify_signature()`) is stateless and works over any
(public_key_pem, signature, payload_hash) triple — callers use it from the
public /verify endpoint without touching the key store.
"""
from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Factory, FactoryKey, KeyProvider, Report, ReportSignature

logger = logging.getLogger(__name__)


class SigningError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------


def get_or_create_active_key(db: Session, factory: Factory) -> FactoryKey:
    """Return the factory's active signing key, creating one if absent."""
    existing = (
        db.query(FactoryKey)
        .filter(FactoryKey.factory_id == factory.id, FactoryKey.active.is_(True))
        .order_by(FactoryKey.created_at.desc())
        .first()
    )
    if existing is not None:
        return existing

    provider = _resolve_provider()
    if provider == KeyProvider.LOCAL:
        key = _generate_local_ed25519(factory.id)
    else:
        key = _register_kms_key(factory.id)

    db.add(key)
    db.flush()
    return key


def _resolve_provider() -> KeyProvider:
    raw = (settings.REPORT_SIGNING_PROVIDER or "local").lower()
    if raw == "kms":
        return KeyProvider.KMS
    if raw == "local":
        return KeyProvider.LOCAL
    raise SigningError(f"unknown REPORT_SIGNING_PROVIDER: {raw!r}")


def _generate_local_ed25519(factory_id: int) -> FactoryKey:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise SigningError("cryptography package not installed") from exc

    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    return FactoryKey(
        factory_id=factory_id,
        provider=KeyProvider.LOCAL,
        algorithm="ed25519",
        public_key_pem=public_pem,
        private_key_pem=private_pem,
        active=True,
    )


def _register_kms_key(factory_id: int) -> FactoryKey:
    """
    Register an existing KMS key ARN as the factory's signing key. We don't
    create KMS keys from the app — that's an infra concern. The operator must
    set AWS_KMS_KEY_ID to the ARN of an existing ECDSA_SHA_256 key that the
    app's IAM role has kms:Sign permission on.
    """
    key_arn = settings.AWS_KMS_KEY_ID
    if not key_arn:
        raise SigningError(
            "REPORT_SIGNING_PROVIDER=kms but AWS_KMS_KEY_ID is not set"
        )

    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise SigningError("boto3 not installed") from exc

    kms = boto3.client("kms", region_name=settings.AWS_REGION)
    resp = kms.get_public_key(KeyId=key_arn)
    # GetPublicKey returns DER — convert to PEM for consistency with local.
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import load_der_public_key

    public_key = load_der_public_key(resp["PublicKey"])
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")

    return FactoryKey(
        factory_id=factory_id,
        provider=KeyProvider.KMS,
        algorithm="ECDSA_SHA_256",
        public_key_pem=public_pem,
        key_arn=key_arn,
        active=True,
    )


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


@dataclass
class SignResult:
    signature_b64: str
    algorithm: str
    provider: KeyProvider
    public_key_pem: str


def sign_payload_hash(factory_key: FactoryKey, payload_hash_hex: str) -> SignResult:
    """
    Sign the raw SHA-256 digest (bytes) of the canonical payload.

    For Ed25519 we sign the full canonical bytes, not the digest — Ed25519 is
    already a two-pass hash internally and signing the digest would be a
    "hash-then-sign-the-hash" antipattern. But we're small and predictable,
    so: local Ed25519 signs the digest-bytes-as-hex-string (treated as bytes);
    KMS ECDSA_SHA_256 signs the raw digest.

    Keep both approaches self-documenting: the signature payload is always
    `hex_digest.encode('ascii')` so the public verify path doesn't need any
    provider-specific knowledge.
    """
    message = payload_hash_hex.encode("ascii")

    if factory_key.provider == KeyProvider.LOCAL:
        return _sign_local(factory_key, message)
    if factory_key.provider == KeyProvider.KMS:
        return _sign_kms(factory_key, message)
    raise SigningError(f"unknown provider: {factory_key.provider}")


def _sign_local(factory_key: FactoryKey, message: bytes) -> SignResult:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if not factory_key.private_key_pem:
        raise SigningError("local factory key has no private material")

    private_key = serialization.load_pem_private_key(
        factory_key.private_key_pem.encode("ascii"),
        password=None,
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise SigningError("expected Ed25519 private key")
    sig = private_key.sign(message)
    return SignResult(
        signature_b64=base64.b64encode(sig).decode("ascii"),
        algorithm="ed25519",
        provider=KeyProvider.LOCAL,
        public_key_pem=factory_key.public_key_pem,
    )


def _sign_kms(factory_key: FactoryKey, message: bytes) -> SignResult:
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise SigningError("boto3 not installed") from exc
    if not factory_key.key_arn:
        raise SigningError("KMS factory key has no key_arn")

    kms = boto3.client("kms", region_name=settings.AWS_REGION)
    resp = kms.sign(
        KeyId=factory_key.key_arn,
        Message=message,
        MessageType="RAW",
        SigningAlgorithm="ECDSA_SHA_256",
    )
    return SignResult(
        signature_b64=base64.b64encode(resp["Signature"]).decode("ascii"),
        algorithm="ECDSA_SHA_256",
        provider=KeyProvider.KMS,
        public_key_pem=factory_key.public_key_pem,
    )


# ---------------------------------------------------------------------------
# High-level: bind signing to a Report row
# ---------------------------------------------------------------------------


def sign_report(db: Session, factory: Factory, report: Report) -> ReportSignature:
    """Produce and persist a signature for the report's payload_hash."""
    if not report.payload_hash:
        raise SigningError("report has no payload_hash yet")

    key = get_or_create_active_key(db, factory)
    result = sign_payload_hash(key, report.payload_hash)

    sig = ReportSignature(
        report_id=report.id,
        factory_key_id=key.id,
        algorithm=result.algorithm,
        provider=result.provider,
        signature_b64=result.signature_b64,
        public_key_pem=result.public_key_pem,
    )
    db.add(sig)
    db.flush()
    logger.info(
        "signed report id=%s factory=%s provider=%s",
        report.id,
        factory.id,
        result.provider.value,
    )
    return sig


# ---------------------------------------------------------------------------
# Verification — public, stateless
# ---------------------------------------------------------------------------


def verify_signature(
    public_key_pem: str,
    algorithm: str,
    signature_b64: str,
    payload_hash_hex: str,
) -> bool:
    """
    Verify `signature_b64` over `payload_hash_hex`.

    Does NOT touch the database — anyone holding the public key, signature,
    and payload hash can call this. That's the whole point of detached
    signatures.
    """
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec, padding
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        raise SigningError("cryptography package not installed")

    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("ascii"))
    except Exception as exc:
        raise SigningError(f"invalid public key PEM: {exc}") from exc

    signature = base64.b64decode(signature_b64)
    message = payload_hash_hex.encode("ascii")

    try:
        algo = algorithm.lower()
        if algo == "ed25519":
            if not isinstance(public_key, Ed25519PublicKey):
                return False
            public_key.verify(signature, message)
            return True
        if algo in ("ecdsa_sha_256", "ecdsa-sha-256"):
            if not isinstance(public_key, ec.EllipticCurvePublicKey):
                return False
            public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
            return True
        raise SigningError(f"unsupported algorithm: {algorithm}")
    except InvalidSignature:
        return False
