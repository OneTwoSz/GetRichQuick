from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from .models import UserRole, FabricType, TransportMode, ReportType


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
    alerts: List[DashboardAlert]


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
