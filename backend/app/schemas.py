from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict
from datetime import datetime
from .models import (
    UserRole,
    FabricType,
    TransportMode,
    ReportType,
    MaterialCategory,
    ProcessType,
    AllocationMethod,
    DataQuality,
    BatchInputType,
    InventoryStatus,
    OrderStatus,
    StockEntryType,
)


# User schemas
class UserBase(BaseModel):
    email: EmailStr
    name: str


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# Factory schemas
class FactoryBase(BaseModel):
    name: str
    location: str
    gst_number: Optional[str] = None
    employee_count: Optional[int] = None
    production_capacity_kg_per_month: Optional[int] = None


class FactoryCreate(FactoryBase):
    pass


class FactoryUpdate(FactoryBase):
    pass


class FactoryResponse(FactoryBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Production Record schemas
class ProductionRecordBase(BaseModel):
    date: datetime
    fabric_type: FabricType
    fabric_quantity_kg: float = Field(gt=0)
    dye_quantity_kg: float = Field(ge=0, default=0)
    chemicals_kg: float = Field(ge=0, default=0)
    electricity_kwh: float = Field(ge=0, default=0)
    water_liters: float = Field(ge=0, default=0)
    wastewater_treated_liters: float = Field(ge=0, default=0)
    garments_produced: int = Field(gt=0)
    transport_distance_km: float = Field(ge=0, default=0)
    transport_mode: Optional[TransportMode] = None
    notes: Optional[str] = None
    product_id: Optional[int] = None


class ProductionRecordCreate(ProductionRecordBase):
    pass


class ProductionRecordUpdate(ProductionRecordBase):
    pass


class ProductionRecordResponse(ProductionRecordBase):
    id: int
    factory_id: int
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


# Product / BOM schemas — per-SKU granularity for DPP readiness.
class BomItemBase(BaseModel):
    material_name: str
    category: MaterialCategory
    material_key: Optional[str] = None
    quantity_per_garment_g: float = Field(gt=0)
    carbon_factor_override: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None


class BomItemCreate(BomItemBase):
    pass


class BomItemResponse(BomItemBase):
    id: int
    product_id: int

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    fiber_composition: Optional[str] = None
    garment_weight_g: float = Field(gt=0)
    cutting_waste_percent: float = Field(default=0, ge=0, lt=100)
    recycled_content_pct: float = Field(default=0, ge=0, le=100)
    care_instructions: Optional[str] = None
    target_buyer: Optional[str] = None
    active: bool = True


class ProductCreate(ProductBase):
    bom: List[BomItemCreate] = Field(default_factory=list)


class ProductUpdate(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: int
    factory_id: int
    created_at: datetime
    bom_items: List[BomItemResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ProductCarbonBreakdown(BaseModel):
    material_name: str
    category: MaterialCategory
    quantity_per_garment_g: float
    carbon_factor: float
    emissions_per_garment_kg: float


class ProductCarbon(BaseModel):
    """Per-garment carbon footprint computed from the BOM (theoretical)."""
    product_id: int
    sku: str
    name: str
    total_per_garment_kg: float
    breakdown: List[ProductCarbonBreakdown]
    # If we have production data tied to this SKU, also surface the actual
    # observed average per-garment carbon for comparison.
    actual_per_garment_kg: Optional[float] = None
    batches_observed: int = 0


# Chemical schemas
class ChemicalBase(BaseModel):
    chemical_name: str
    supplier: Optional[str] = None
    quantity_kg: float = Field(gt=0)
    cas_number: Optional[str] = None
    reach_compliant: bool = False
    zdhc_compliant: bool = False
    certificate_url: Optional[str] = None
    expiry_date: Optional[datetime] = None


class ChemicalCreate(ChemicalBase):
    pass


class ChemicalUpdate(ChemicalBase):
    pass


class ChemicalResponse(ChemicalBase):
    id: int
    factory_id: int
    last_updated: datetime

    class Config:
        from_attributes = True


# Report schemas
class ReportCreate(BaseModel):
    date_from: datetime
    date_to: datetime
    report_type: ReportType = ReportType.MONTHLY


class ReportResponse(BaseModel):
    id: int
    factory_id: int
    report_type: ReportType
    date_from: datetime
    date_to: datetime
    total_carbon_kg: float
    carbon_per_garment_kg: float
    water_per_garment_liters: float
    pdf_url: Optional[str] = None
    generated_by: int
    created_at: datetime

    class Config:
        from_attributes = True


# Carbon footprint schemas
class CarbonBreakdown(BaseModel):
    materials: float
    energy: float
    water_treatment: float
    chemicals: float
    transport: float


class CarbonSummary(BaseModel):
    total_carbon_kg: float
    carbon_per_garment_kg: float
    breakdown: CarbonBreakdown
    total_garments: int
    date_from: datetime
    date_to: datetime


# Water & Energy schemas
class WaterEnergyMetrics(BaseModel):
    month: str
    water_per_garment_liters: float
    electricity_per_garment_kwh: float
    total_water_liters: float
    total_electricity_kwh: float


class WaterEnergyTrends(BaseModel):
    metrics: List[WaterEnergyMetrics]


# Dashboard schemas
class DashboardAlert(BaseModel):
    type: str  # "chemical_compliance", "missing_data", etc.
    severity: str  # "high", "medium", "low"
    message: str


class DashboardSummary(BaseModel):
    carbon_footprint_this_month: float
    water_usage_this_month: float
    chemical_compliance_percentage: float
    reports_generated: int
    # Phase 2: rework batches ÷ total batches (0..1).
    rework_rate: float = 0
    alerts: List[DashboardAlert]


# ---------------------------------------------------------------------------
# Phase 2 — orders, batches, allocation
# ---------------------------------------------------------------------------


class OrderBase(BaseModel):
    order_code: str
    buyer_name: Optional[str] = None
    product_id: int
    units: int = Field(gt=0)
    order_value: Optional[float] = Field(default=None, gt=0)
    status: OrderStatus = OrderStatus.OPEN
    notes: Optional[str] = None


class OrderCreate(OrderBase):
    pass


class OrderUpdate(OrderBase):
    pass


class OrderResponse(OrderBase):
    id: int
    factory_id: int
    share_token: Optional[str] = None
    created_at: datetime
    # Computed: units × net garment weight ÷ (1 − waste%), per style.
    fabric_demand_kg: Optional[float] = None

    class Config:
        from_attributes = True


class JobWorkerBase(BaseModel):
    name: str
    process_type: ProcessType
    location: Optional[str] = None
    contact: Optional[str] = None


class JobWorkerCreate(JobWorkerBase):
    pass


class JobWorkerResponse(JobWorkerBase):
    id: int
    factory_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BatchInputBase(BaseModel):
    input_type: BatchInputType
    chemical_id: Optional[int] = None
    quantity: float = Field(gt=0)
    data_quality: DataQuality = DataQuality.MEASURED
    source: Optional[str] = None


class BatchInputCreate(BatchInputBase):
    pass


class BatchInputResponse(BatchInputBase):
    id: int
    batch_id: int

    class Config:
        from_attributes = True


class BatchAllocationResponse(BaseModel):
    id: int
    batch_id: int
    order_id: int
    product_id: Optional[int] = None
    fabric_kg: float
    garment_units: Optional[int] = None
    order_value: Optional[float] = None
    allocated_share: float

    class Config:
        from_attributes = True


class ProductionBatchBase(BaseModel):
    batch_code: str
    process_type: ProcessType
    colour: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_fabric_kg: float = Field(gt=0)
    is_rework: bool = False
    rework_of_batch_id: Optional[int] = None
    allocation_method: AllocationMethod = AllocationMethod.MASS
    allocation_note: Optional[str] = None
    outsourced: bool = False
    job_worker_id: Optional[int] = None


class ProductionBatchCreate(ProductionBatchBase):
    inputs: List[BatchInputCreate] = Field(default_factory=list)


class ProductionBatchUpdate(ProductionBatchBase):
    pass


class ProductionBatchResponse(ProductionBatchBase):
    id: int
    factory_id: int
    job_work_token: Optional[str] = None
    created_at: datetime
    inputs: List[BatchInputResponse] = Field(default_factory=list)
    allocations: List[BatchAllocationResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class AttachOrderLine(BaseModel):
    order_id: int
    # Omit to auto-compute from the order's style: units × net weight ÷
    # (1 − cutting waste%). Provide to override (partial coverage etc.).
    fabric_kg: Optional[float] = Field(default=None, gt=0)


class AttachOrdersRequest(BaseModel):
    lines: List[AttachOrderLine] = Field(min_length=1)


class BatchLineOut(BaseModel):
    batch_id: int
    batch_code: str
    process_type: str
    allocation_method: str
    allocated_share: float
    co2_kg: float
    water_l: float
    is_rework: bool
    outsourced: bool
    data_quality_flags: List[str] = Field(default_factory=list)
    allocation_note: Optional[str] = None


class OrderFootprintResponse(BaseModel):
    """Footprint + Allocation Statement + data-quality mix — the payload
    both the factory UI and the buyer share link render."""
    order_id: int
    order_code: str
    buyer_name: Optional[str] = None
    product_sku: Optional[str] = None
    product_name: Optional[str] = None
    units: int
    co2_kg: float
    co2_per_garment_kg: float
    water_l: float
    water_per_garment_l: float
    batch_lines: List[BatchLineOut]
    embodied_co2_kg: float
    embodied_water_l: float
    overhead_co2_kg: float
    overhead_water_l: float
    quality_mix: Dict[str, float]
    used_economic_allocation: bool


class FabricInventoryResponse(BaseModel):
    id: int
    factory_id: int
    source_batch_id: int
    fabric_kg: float
    embodied_co2_kg: float
    embodied_water_l: float
    status: InventoryStatus
    consumed_by_order_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConsumeInventoryRequest(BaseModel):
    order_id: int


class WriteOffInventoryRequest(BaseModel):
    status: InventoryStatus = InventoryStatus.WASTE  # WASTE or SOLD


class MonthlyUtilityCreate(BaseModel):
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)
    total_electricity_kwh: float = Field(ge=0)
    total_water_liters: float = Field(ge=0)
    note: Optional[str] = None


class MonthlyUtilityResponse(MonthlyUtilityCreate):
    id: int
    factory_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BatchOverheadOut(BaseModel):
    batch_code: str
    fabric_kg: float
    overhead_kwh: float
    overhead_water_l: float


class ReconciliationResponse(BaseModel):
    year: int
    month: int
    total_electricity_kwh: float
    total_water_liters: float
    attributed_kwh: float
    attributed_water_l: float
    overhead_kwh: float
    overhead_water_l: float
    total_fabric_kg: float
    per_batch: Dict[int, BatchOverheadOut]


class JobWorkSubmission(BaseModel):
    """What a job worker posts through the login-free token link."""
    inputs: List[BatchInputCreate] = Field(min_length=1)
    submitted_by: Optional[str] = None  # free-text name/phone for the trail


class ChemicalStockEntryCreate(BaseModel):
    chemical_id: int
    entry_type: StockEntryType
    quantity_kg: float
    note: Optional[str] = None


class ChemicalStockEntryResponse(ChemicalStockEntryCreate):
    id: int
    factory_id: int
    batch_input_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChemicalStockBalance(BaseModel):
    chemical_id: int
    chemical_name: str
    balance_kg: float
    reach_compliant: bool
    zdhc_compliant: bool


# Audit Log schemas
class AuditLogResponse(BaseModel):
    id: int
    factory_id: int
    user_id: int
    action: str
    entity_type: str
    entity_id: int
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    timestamp: datetime

    class Config:
        from_attributes = True
