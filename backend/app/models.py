from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    FACTORY_MANAGER = "factory_manager"


class FabricType(str, enum.Enum):
    COTTON = "cotton"
    POLYESTER = "polyester"
    BLEND = "blend"
    ORGANIC_COTTON = "organic_cotton"


class TransportMode(str, enum.Enum):
    TRUCK = "truck"
    SEA_FREIGHT = "sea_freight"


class ReportType(str, enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    CUSTOM = "custom"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.FACTORY_MANAGER, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    factory = relationship("Factory", back_populates="user", uselist=False)


class Factory(Base):
    __tablename__ = "factories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    gst_number = Column(String, unique=True)
    employee_count = Column(Integer)
    production_capacity_kg_per_month = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="factory")
    production_records = relationship("ProductionRecord", back_populates="factory", cascade="all, delete-orphan")
    chemicals = relationship("Chemical", back_populates="factory", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="factory", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="factory", cascade="all, delete-orphan")


class ProductionRecord(Base):
    __tablename__ = "production_records"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    fabric_type = Column(Enum(FabricType), nullable=False)
    fabric_quantity_kg = Column(Float, nullable=False)
    dye_quantity_kg = Column(Float, default=0)
    chemicals_kg = Column(Float, default=0)
    electricity_kwh = Column(Float, default=0)
    water_liters = Column(Float, default=0)
    wastewater_treated_liters = Column(Float, default=0)
    garments_produced = Column(Integer, nullable=False)
    transport_distance_km = Column(Float, default=0)
    transport_mode = Column(Enum(TransportMode), nullable=True)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    factory = relationship("Factory", back_populates="production_records")


class Chemical(Base):
    __tablename__ = "chemicals"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    chemical_name = Column(String, nullable=False)
    supplier = Column(String)
    quantity_kg = Column(Float, nullable=False)
    cas_number = Column(String)
    reach_compliant = Column(Boolean, default=False)
    zdhc_compliant = Column(Boolean, default=False)
    certificate_url = Column(String)
    expiry_date = Column(DateTime(timezone=True))
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    factory = relationship("Factory", back_populates="chemicals")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    report_type = Column(Enum(ReportType), default=ReportType.MONTHLY, nullable=False)
    date_from = Column(DateTime(timezone=True), nullable=False)
    date_to = Column(DateTime(timezone=True), nullable=False)
    total_carbon_kg = Column(Float, nullable=False)
    carbon_per_garment_kg = Column(Float, nullable=False)
    water_per_garment_liters = Column(Float, nullable=False)
    pdf_url = Column(String)
    # SHA-256 of the canonical JSON payload used to generate the PDF.
    # This is the exact byte sequence the signature was computed over.
    payload_hash = Column(String, index=True)
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Link to the day's Merkle anchor, populated by the daily job.
    merkle_anchor_id = Column(Integer, ForeignKey("merkle_anchors.id"), nullable=True, index=True)

    # Relationships
    factory = relationship("Factory", back_populates="reports")
    signature = relationship(
        "ReportSignature",
        uselist=False,
        back_populates="report",
        cascade="all, delete-orphan",
    )
    merkle_anchor = relationship("MerkleAnchor", back_populates="reports")


# ---------------------------------------------------------------------------
# Signing / anchoring (added for verifiable reports)
# ---------------------------------------------------------------------------


class KeyProvider(str, enum.Enum):
    """Where the signing key material lives."""
    LOCAL = "local"   # Ed25519 private key stored encrypted in the DB (dev/SMB-tier)
    KMS = "kms"       # AWS KMS — the DB only stores a key ARN, never the secret


class FactoryKey(Base):
    """
    One signing key per factory. We keep the key rowboat-simple: public key as
    PEM, plus either an encrypted local private key or a KMS key ARN.

    Rotation: create a new row with `active=True` and mark the old one False.
    Old reports remain verifiable because `ReportSignature` persists the public
    key bytes actually used at signing time.
    """
    __tablename__ = "factory_keys"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    provider = Column(Enum(KeyProvider), nullable=False)
    algorithm = Column(String, nullable=False)  # 'ed25519' or 'ECDSA_SHA_256'
    public_key_pem = Column(Text, nullable=False)
    # For provider=local: PEM of the private key, encrypted-at-rest is out of
    # scope for dev (file-level / pg-level encryption handles it). For KMS,
    # this is NULL and key_arn is used.
    private_key_pem = Column(Text, nullable=True)
    key_arn = Column(String, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReportSignature(Base):
    """
    Detached signature for a Report's canonical payload hash.

    We persist:
      - signature bytes (base64)
      - the public key that corresponds to the private key that signed it
        (snapshotted so verification survives key rotation)
      - the algorithm used
      - which provider did the signing
    """
    __tablename__ = "report_signatures"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), unique=True, nullable=False)
    factory_key_id = Column(Integer, ForeignKey("factory_keys.id"), nullable=False)
    algorithm = Column(String, nullable=False)
    provider = Column(Enum(KeyProvider), nullable=False)
    signature_b64 = Column(Text, nullable=False)
    public_key_pem = Column(Text, nullable=False)
    signed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    report = relationship("Report", back_populates="signature")


class MerkleAnchor(Base):
    """
    One row per day we bundle up report hashes into a Merkle tree and submit
    the root to OpenTimestamps (Bitcoin). The OTS proof is a blob we get back
    asynchronously — we persist it once the upgrade completes.

    Reports get `merkle_anchor_id` stamped by the daily job so the public
    verify endpoint can serve the inclusion proof.
    """
    __tablename__ = "merkle_anchors"

    id = Column(Integer, primary_key=True, index=True)
    # UTC date the batch covers (YYYY-MM-DD stored as midnight UTC).
    anchor_date = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)
    merkle_root_hex = Column(String, nullable=False)
    leaf_count = Column(Integer, nullable=False)
    # Serialized inclusion proofs, keyed by leaf hash:
    #   { "<payload_hash_hex>": ["<sibling_hex>:L", "<sibling_hex>:R", ...] }
    inclusion_proofs = Column(JSON, nullable=False)
    # Raw OTS proof bytes (hex) — null until OpenTimestamps upgrades it with
    # the Bitcoin attestation.
    ots_proof_hex = Column(Text, nullable=True)
    ots_submitted_at = Column(DateTime(timezone=True), nullable=True)
    ots_upgraded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    reports = relationship("Report", back_populates="merkle_anchor")


class AuditLog(Base):
    """
    Append-only audit log with SHA-256 hash chaining.

    Each row's `payload_hash` is sha256(canonical JSON of the row's content +
    prev_hash). This lets anyone detect tampering: if you flip a cell, every
    subsequent row's hash no longer matches. We take a daily Merkle root of
    the tip hash per factory into OpenTimestamps so the chain is anchored to
    Bitcoin.

    prev_hash is nullable for the very first row per factory.
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)  # CREATE, UPDATE, DELETE
    entity_type = Column(String, nullable=False)  # production_record, chemical, etc.
    entity_id = Column(Integer, nullable=False)
    old_value = Column(JSON)
    new_value = Column(JSON)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Hash chain — nullable to preserve backwards compatibility with pre-
    # chaining rows. New rows MUST populate both.
    prev_hash = Column(String, nullable=True)
    payload_hash = Column(String, nullable=True, index=True)

    # Relationships
    factory = relationship("Factory", back_populates="audit_logs")
