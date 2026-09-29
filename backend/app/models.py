from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Text, JSON, UniqueConstraint
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


class MaterialCategory(str, enum.Enum):
    """Coarse buckets for BOM line items, used to look up an emission factor.

    Kept deliberately flat so factories can describe a real garment without
    needing an LCA-grade taxonomy. The category drives the carbon factor when
    a BOM item doesn't supply its own override.
    """
    FIBER = "fiber"          # cotton, polyester, blend, etc. — uses fabric factors
    DYE = "dye"
    CHEMICAL = "chemical"     # softeners, salts, fixatives
    TRIM = "trim"             # buttons, labels, sewing thread, zippers


class ReportType(str, enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Phase 2 enums — production batches & allocation
# ---------------------------------------------------------------------------


class ProcessType(str, enum.Enum):
    KNITTING = "knitting"
    BLEACHING = "bleaching"
    DYEING = "dyeing"
    PRINTING = "printing"
    FINISHING = "finishing"
    CUTTING_SEWING = "cutting_sewing"


class AllocationMethod(str, enum.Enum):
    """ISO 14044 hierarchy rungs. MASS is the default for wet processing
    (impact scales with fabric mass); UNITS when garments are near-identical
    in weight; ECONOMIC only as a fallback — reports flag it."""
    MASS = "mass"
    UNITS = "units"
    ECONOMIC = "economic"


class DataQuality(str, enum.Enum):
    """Primary-vs-secondary data tiering, the axis DPP/buyer frameworks care
    about. Every batch input carries one; reports show the mix."""
    MEASURED = "measured"          # meter reading, weighed drawdown
    ESTIMATED = "estimated"        # derived from a bill (utility, job-work)
    DEFAULT_FACTOR = "default_factor"  # built-in per-process default


class BatchInputType(str, enum.Enum):
    WATER_L = "water_l"
    ELECTRICITY_KWH = "electricity_kwh"
    CHEMICAL_KG = "chemical_kg"
    DYE_KG = "dye_kg"
    STEAM_KG = "steam_kg"
    DIESEL_L = "diesel_l"


class InventoryStatus(str, enum.Enum):
    IN_STOCK = "in_stock"
    CONSUMED = "consumed"
    SOLD = "sold"
    WASTE = "waste"


class OrderStatus(str, enum.Enum):
    OPEN = "open"
    IN_PRODUCTION = "in_production"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WasteDestination(str, enum.Enum):
    """Where cutting waste goes. Tiruppur waste usually feeds the recycling
    trade — recording it improves the circularity story on reports."""
    RECYCLER = "recycler"
    LANDFILL = "landfill"
    REUSED = "reused"


class StockEntryType(str, enum.Enum):
    PURCHASE = "purchase"
    DRAWDOWN = "drawdown"
    RECONCILIATION = "reconciliation"


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
    # Where this factory's cutting waste ends up (see WasteDestination).
    # Factory-level because the destination is a standing arrangement
    # (e.g. a recycler contract), not a per-batch decision.
    cutting_waste_destination = Column(Enum(WasteDestination), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="factory")
    production_records = relationship("ProductionRecord", back_populates="factory", cascade="all, delete-orphan")
    chemicals = relationship("Chemical", back_populates="factory", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="factory", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="factory", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="factory", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="factory", cascade="all, delete-orphan")
    production_batches = relationship("ProductionBatch", back_populates="factory", cascade="all, delete-orphan")
    job_workers = relationship("JobWorker", back_populates="factory", cascade="all, delete-orphan")


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
    # Optional link to a Product (SKU). Nullable because we still allow
    # untyped batch entries while a factory backfills its catalog. When set,
    # the batch's emissions get attributed to that product for per-SKU rollups.
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    factory = relationship("Factory", back_populates="production_records")
    product = relationship("Product", back_populates="production_records")


class Product(Base):
    """A SKU / style produced by the factory.

    The DPP unit of granularity is per-SKU, so each row here represents one
    product the factory makes (e.g. "Crew tee, organic cotton, 180 GSM"). The
    BOM table lists the materials that go into one garment.
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    sku = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    # Free-text fiber composition like "95% organic cotton, 5% elastane".
    # Kept as a string for v1 — DPP will eventually want structured percentages.
    fiber_composition = Column(String, nullable=True)
    garment_weight_g = Column(Float, nullable=False)
    # Marker efficiency differs by style — knitwear cutting waste commonly
    # runs 15–25%. Percent (0–100). Fabric demand for an order of this style
    # = units × (garment_weight_g/1000) ÷ (1 − waste/100), so wasteful styles
    # correctly carry more of a shared batch's footprint.
    cutting_waste_percent = Column(Float, default=0, nullable=False)
    recycled_content_pct = Column(Float, default=0)
    care_instructions = Column(Text, nullable=True)
    target_buyer = Column(String, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    # Passport presentation (Phase 3). Nullable so database.add_missing_columns
    # can add them to databases created before they existed.
    image_url = Column(String, nullable=True)       # "/api/media/<file>"
    image_sha256 = Column(String, nullable=True)    # pinned into signed passports
    care_symbols = Column(JSON, nullable=True)      # ["wash_30", "do_not_bleach", ...]
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    factory = relationship("Factory", back_populates="products")
    bom_items = relationship(
        "BillOfMaterialsItem",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="BillOfMaterialsItem.id",
    )
    production_records = relationship("ProductionRecord", back_populates="product")


class BillOfMaterialsItem(Base):
    """One line in the bill of materials for a Product.

    quantity_per_garment_g is the per-unit input. carbon_factor_override lets
    a factory plug in a supplier-specific value (e.g. recycled-PET yarn from
    a vendor with an EPD); when null we fall back to the category lookup.
    """
    __tablename__ = "bom_items"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    material_name = Column(String, nullable=False)
    category = Column(Enum(MaterialCategory), nullable=False)
    # The lookup key for the carbon factor, e.g. "cotton", "organic_cotton",
    # "polyester", "recycled_polyester", "elastane", or a free string like
    # "reactive_dye". Falls back to a generic factor for the category.
    material_key = Column(String, nullable=True)
    quantity_per_garment_g = Column(Float, nullable=False)
    carbon_factor_override = Column(Float, nullable=True)  # kg CO2e per kg
    notes = Column(Text, nullable=True)

    product = relationship("Product", back_populates="bom_items")


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


# ---------------------------------------------------------------------------
# Phase 2 — Production batches & allocation
#
# Field reality: when two orders need the same fabric, the factory runs ALL
# of it in one combined lot — one dye bath, shared water/power/chemicals.
# Consumption is only measurable at the batch (or facility) level, never per
# order. So resources are logged against a ProductionBatch; an allocation
# engine (services/allocation.py) splits batch consumption across the orders
# the batch served.
# ---------------------------------------------------------------------------


class Order(Base):
    """A buyer order for N units of one style. The unit the footprint is
    ultimately reported against — but never the unit data is entered at."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    order_code = Column(String, nullable=False)
    buyer_name = Column(String, nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    units = Column(Integer, nullable=False)
    # Only needed when a batch uses ECONOMIC allocation.
    order_value = Column(Float, nullable=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.OPEN, nullable=False)
    # Buyer-facing read-only share link token. Generated on demand; the
    # public endpoint serves footprint + allocation statement + data-quality
    # mix so the factory can answer any brand portal request in one click.
    share_token = Column(String, unique=True, nullable=True, index=True)
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    factory = relationship("Factory", back_populates="orders")
    product = relationship("Product")
    allocations = relationship("BatchAllocation", back_populates="order", cascade="all, delete-orphan")


class JobWorker(Base):
    """Outsourced processor (dyeing unit, CETP...). Very Tiruppur-specific:
    dyeing is frequently job-worked and the manufacturer has no primary data
    for that step — batches flagged outsourced point here."""
    __tablename__ = "job_workers"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    process_type = Column(Enum(ProcessType), nullable=False)
    location = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    factory = relationship("Factory", back_populates="job_workers")


class ProductionBatch(Base):
    """One physical production run (a lot). Resources attach here; orders
    attach here; the allocation engine does the splitting."""
    __tablename__ = "production_batches"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    batch_code = Column(String, nullable=False)  # e.g. "LOT-2026-0714-WHT"
    process_type = Column(Enum(ProcessType), nullable=False)
    colour = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    total_fabric_kg = Column(Float, nullable=False)
    # Re-dye / re-process runs. Routine, roughly doubles water/energy/
    # chemicals for the lot — inputs of a rework batch are ADDED to the
    # original batch's order allocations pro rata. Do not hide it.
    is_rework = Column(Boolean, default=False, nullable=False)
    rework_of_batch_id = Column(Integer, ForeignKey("production_batches.id"), nullable=True)
    allocation_method = Column(Enum(AllocationMethod), default=AllocationMethod.MASS, nullable=False)
    allocation_note = Column(Text, nullable=True)  # free text, printed in audit trail
    # Job-work: the batch ran at an outside unit. A token URL lets the job
    # worker submit actual consumption without a login (data path 1 of §5).
    outsourced = Column(Boolean, default=False, nullable=False)
    job_worker_id = Column(Integer, ForeignKey("job_workers.id"), nullable=True)
    job_work_token = Column(String, unique=True, nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    factory = relationship("Factory", back_populates="production_batches")
    job_worker = relationship("JobWorker")
    rework_of = relationship("ProductionBatch", remote_side=[id], backref="reworks")
    inputs = relationship("BatchInput", back_populates="batch", cascade="all, delete-orphan")
    allocations = relationship("BatchAllocation", back_populates="batch", cascade="all, delete-orphan")


class BatchInput(Base):
    """One resource drawn by a batch — a meter reading, a chemical drawdown,
    a diesel top-up. `data_quality` tags how the number was obtained."""
    __tablename__ = "batch_inputs"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("production_batches.id"), nullable=False, index=True)
    input_type = Column(Enum(BatchInputType), nullable=False)
    # FK to chemical inventory when input_type is CHEMICAL_KG / DYE_KG —
    # links compliance status (REACH/ZDHC) onto every batch that used it.
    chemical_id = Column(Integer, ForeignKey("chemicals.id"), nullable=True)
    quantity = Column(Float, nullable=False)
    data_quality = Column(Enum(DataQuality), default=DataQuality.MEASURED, nullable=False)
    source = Column(String, nullable=True)  # "meter reading", "utility bill", "supplier declaration"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    batch = relationship("ProductionBatch", back_populates="inputs")
    chemical = relationship("Chemical")


class BatchAllocation(Base):
    """One order's slice of a batch. `allocated_share` is computed by the
    engine and stored for audit immutability — reports print what was used
    at the time, even if the batch is edited later."""
    __tablename__ = "batch_allocations"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("production_batches.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    # Style snapshot at allocation time (order.product_id can change).
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    fabric_kg = Column(Float, nullable=False)  # incl. this style's cutting waste
    garment_units = Column(Integer, nullable=True)
    order_value = Column(Float, nullable=True)  # only needed for ECONOMIC
    allocated_share = Column(Float, nullable=False)  # 0..1, stored for audit

    batch = relationship("ProductionBatch", back_populates="allocations")
    order = relationship("Order", back_populates="allocations")


class FabricInventory(Base):
    """Leftover / buffer fabric from a batch (factories over-produce ~3–5%).
    Carries its pro-rata embodied footprint so nothing vanishes: consuming
    it later transfers the footprint to that order; writing it off books it
    to the factory waste ledger."""
    __tablename__ = "fabric_inventory"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    source_batch_id = Column(Integer, ForeignKey("production_batches.id"), nullable=False)
    fabric_kg = Column(Float, nullable=False)
    embodied_co2_kg = Column(Float, nullable=False)
    embodied_water_l = Column(Float, nullable=False)
    status = Column(Enum(InventoryStatus), default=InventoryStatus.IN_STOCK, nullable=False)
    consumed_by_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    source_batch = relationship("ProductionBatch")
    consumed_by_order = relationship("Order")


class ChemicalStockEntry(Base):
    """Ledger over the existing Chemical master records: purchases add
    stock, batch drawdowns subtract, periodic physical reconciliation
    books the variance (spread as overhead)."""
    __tablename__ = "chemical_stock_entries"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    chemical_id = Column(Integer, ForeignKey("chemicals.id"), nullable=False, index=True)
    entry_type = Column(Enum(StockEntryType), nullable=False)
    # Signed: purchases positive, drawdowns negative, reconciliation either.
    quantity_kg = Column(Float, nullable=False)
    batch_input_id = Column(Integer, ForeignKey("batch_inputs.id"), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chemical = relationship("Chemical")


class MonthlyUtility(Base):
    """The single-meter problem: one electricity meter, one water line.
    Monthly bill totals go here; reconciliation computes
    monthly total − Σ(batch-attributed inputs) = facility overhead, spread
    across the month's output by mass. Factories with zero sub-metering run
    "overhead only": everything top-down — lower data-quality tier, but
    honest and usable on day one."""
    __tablename__ = "monthly_utilities"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1..12
    total_electricity_kwh = Column(Float, default=0, nullable=False)
    total_water_liters = Column(Float, default=0, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Phase 3 — product life cycle, supply chain, digital product passport
#
# All new tables (no columns added to existing ones) so databases created
# before Phase 3 keep working: init_db()'s create_all adds these on start.
# ---------------------------------------------------------------------------


class SupplyChainStage(str, enum.Enum):
    """Upstream stages a supplier can perform. Mirrors the life-cycle
    engine's stage keys (services/lifecycle.py)."""
    RAW_MATERIALS = "raw_materials"
    YARN_PRODUCTION = "yarn_production"
    FABRIC_PRODUCTION = "fabric_production"
    WET_PROCESSING = "wet_processing"
    ASSEMBLY = "assembly"
    TRIMS_PACKAGING = "trims_packaging"


# Conventional apparel tiering: Tier 1 finished goods, Tier 2 fabric and
# wet processing (and trims), Tier 3 yarn, Tier 4 raw fibre.
STAGE_TIER = {
    SupplyChainStage.ASSEMBLY: 1,
    SupplyChainStage.FABRIC_PRODUCTION: 2,
    SupplyChainStage.WET_PROCESSING: 2,
    SupplyChainStage.TRIMS_PACKAGING: 2,
    SupplyChainStage.YARN_PRODUCTION: 3,
    SupplyChainStage.RAW_MATERIALS: 4,
}


class Supplier(Base):
    """An upstream facility in the factory's supply chain (spinner, knitter,
    dye house, fibre trader, trims vendor). Certifications are a JSON list
    of {"name", "number", "valid_until"} — GOTS, OEKO-TEX, GRS, BCI..."""
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    stage = Column(Enum(SupplyChainStage), nullable=False)
    tier = Column(Integer, nullable=False)
    country = Column(String(2), nullable=False, default="IN")  # ISO-3166 alpha-2
    city = Column(String, nullable=True)
    certifications = Column(JSON, nullable=False, default=list)
    contact = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    submissions = relationship("SupplierSubmission", back_populates="supplier",
                               cascade="all, delete-orphan")


class ProductSupplier(Base):
    """Which supplier performs which upstream stage for a product. One
    supplier per stage per product — the traceability map a passport shows."""
    __tablename__ = "product_suppliers"
    __table_args__ = (UniqueConstraint("product_id", "stage", name="uq_product_stage"),)

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True)
    stage = Column(Enum(SupplyChainStage), nullable=False)

    supplier = relationship("Supplier")


class SupplierDataRequest(Base):
    """A login-free token link asking a supplier for a period's resource
    use at one stage — the upstream twin of the job-work link."""
    __tablename__ = "supplier_data_requests"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True)
    stage = Column(Enum(SupplyChainStage), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    period_label = Column(String, nullable=True)  # e.g. "Apr–Jun 2026"
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    supplier = relationship("Supplier")


class SupplierSubmission(Base):
    """A supplier's facility totals for a period at one stage. Intensity
    per kg = each input ÷ output_kg; the life-cycle engine applies it to
    the product's mass at that stage."""
    __tablename__ = "supplier_submissions"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("supplier_data_requests.id"), nullable=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, index=True)
    stage = Column(Enum(SupplyChainStage), nullable=False)
    period_label = Column(String, nullable=True)
    output_kg = Column(Float, nullable=False)
    electricity_kwh = Column(Float, default=0, nullable=False)
    water_l = Column(Float, default=0, nullable=False)
    steam_kg = Column(Float, default=0, nullable=False)
    diesel_l = Column(Float, default=0, nullable=False)
    chemical_kg = Column(Float, default=0, nullable=False)
    dye_kg = Column(Float, default=0, nullable=False)
    data_quality = Column(Enum(DataQuality), default=DataQuality.ESTIMATED, nullable=False)
    submitted_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    supplier = relationship("Supplier", back_populates="submissions")


class ProductLifecycle(Base):
    """Per-product life-cycle settings beyond the factory gate: system
    boundary, packaging, distribution legs, use and end-of-life scenario."""
    __tablename__ = "product_lifecycle"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), unique=True, nullable=False)
    boundary = Column(String, default="cradle_to_gate", nullable=False)
    packaging = Column(JSON, nullable=False, default=list)      # [{material_key, grams}]
    distribution = Column(JSON, nullable=False, default=list)   # [{mode, distance_km}]
    washes = Column(Integer, default=0, nullable=False)
    tumble_dry = Column(Boolean, default=False, nullable=False)
    use_country = Column(String(2), default="EU", nullable=False)
    end_of_life = Column(String, default="eu_average", nullable=False)


class ProductPassport(Base):
    """The public Digital Product Passport for a product. Content lives in
    immutable, signed PassportVersion rows; the token is what the QR code
    on the garment label resolves to."""
    __tablename__ = "product_passports"

    id = Column(Integer, primary_key=True, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), unique=True, nullable=False)
    public_token = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    versions = relationship("PassportVersion", back_populates="passport",
                            cascade="all, delete-orphan", order_by="PassportVersion.version")


class PassportVersion(Base):
    """One published snapshot. The payload is hashed (canonical JSON) and
    signed with the factory key, so anyone can check the passport they are
    reading is exactly what the factory published and signed off."""
    __tablename__ = "passport_versions"

    id = Column(Integer, primary_key=True, index=True)
    passport_id = Column(Integer, ForeignKey("product_passports.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    payload = Column(JSON, nullable=False)
    payload_hash = Column(String, nullable=False, index=True)
    factory_key_id = Column(Integer, ForeignKey("factory_keys.id"), nullable=False)
    algorithm = Column(String, nullable=False)
    signature_b64 = Column(Text, nullable=False)
    public_key_pem = Column(Text, nullable=False)
    reviewed_by_name = Column(String, nullable=False)
    review_note = Column(Text, nullable=True)
    published_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    published_at = Column(DateTime(timezone=True), server_default=func.now())

    passport = relationship("ProductPassport", back_populates="versions")
