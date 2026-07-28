// User types
export interface User {
  id: number;
  email: string;
  name: string;
  role: 'admin' | 'factory_manager';
  created_at: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  name: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

// Factory types
export interface Factory {
  id: number;
  user_id: number;
  name: string;
  location: string;
  gst_number?: string;
  employee_count?: number;
  production_capacity_kg_per_month?: number;
  created_at: string;
}

export interface FactoryFormData {
  name: string;
  location: string;
  gst_number?: string;
  employee_count?: number;
  production_capacity_kg_per_month?: number;
}

// Production Record types
export type FabricType = 'cotton' | 'polyester' | 'blend' | 'organic_cotton';
export type TransportMode = 'truck' | 'sea_freight';

export interface ProductionRecord {
  id: number;
  factory_id: number;
  date: string;
  fabric_type: FabricType;
  fabric_quantity_kg: number;
  dye_quantity_kg: number;
  chemicals_kg: number;
  electricity_kwh: number;
  water_liters: number;
  wastewater_treated_liters: number;
  garments_produced: number;
  transport_distance_km: number;
  transport_mode?: TransportMode;
  notes?: string;
  created_by: number;
  created_at: string;
}

export interface ProductionFormData {
  date: string;
  fabric_type: FabricType;
  fabric_quantity_kg: number;
  dye_quantity_kg: number;
  chemicals_kg: number;
  electricity_kwh: number;
  water_liters: number;
  wastewater_treated_liters: number;
  garments_produced: number;
  transport_distance_km: number;
  transport_mode?: TransportMode;
  notes?: string;
}

// Chemical types
export interface Chemical {
  id: number;
  factory_id: number;
  chemical_name: string;
  supplier?: string;
  quantity_kg: number;
  cas_number?: string;
  reach_compliant: boolean;
  zdhc_compliant: boolean;
  certificate_url?: string;
  expiry_date?: string;
  last_updated: string;
}

export interface ChemicalFormData {
  chemical_name: string;
  supplier?: string;
  quantity_kg: number;
  cas_number?: string;
  reach_compliant: boolean;
  zdhc_compliant: boolean;
  certificate_url?: string;
  expiry_date?: string;
}

// Carbon types
export interface CarbonBreakdown {
  materials: number;
  energy: number;
  water_treatment: number;
  chemicals: number;
  transport: number;
}

export interface CarbonSummary {
  total_carbon_kg: number;
  carbon_per_garment_kg: number;
  breakdown: CarbonBreakdown;
  total_garments: number;
  date_from: string;
  date_to: string;
}

// Water & Energy types
export interface WaterEnergyMetrics {
  month: string;
  water_per_garment_liters: number;
  electricity_per_garment_kwh: number;
  total_water_liters: number;
  total_electricity_kwh: number;
}

export interface WaterEnergyTrends {
  metrics: WaterEnergyMetrics[];
}

// Report types
export type ReportType = 'monthly' | 'quarterly' | 'custom';

export interface Report {
  id: number;
  factory_id: number;
  report_type: ReportType;
  date_from: string;
  date_to: string;
  total_carbon_kg: number;
  carbon_per_garment_kg: number;
  water_per_garment_liters: number;
  pdf_url?: string;
  generated_by: number;
  created_at: string;
}

export interface ReportFormData {
  date_from: string;
  date_to: string;
  report_type: ReportType;
}

// Dashboard types
export interface DashboardAlert {
  type: string;
  severity: 'high' | 'medium' | 'low';
  message: string;
}

export interface DashboardSummary {
  carbon_footprint_this_month: number;
  water_usage_this_month: number;
  chemical_compliance_percentage: number;
  reports_generated: number;
  /** Phase 2: rework batches ÷ total batches (0..1). */
  rework_rate?: number;
  alerts: DashboardAlert[];
}

// Product / BOM types — per-SKU granularity for DPP readiness.
export type MaterialCategory = 'fiber' | 'dye' | 'chemical' | 'trim';

export interface BomItem {
  id: number;
  product_id: number;
  material_name: string;
  category: MaterialCategory;
  material_key?: string | null;
  quantity_per_garment_g: number;
  carbon_factor_override?: number | null;
  notes?: string | null;
}

export interface Product {
  id: number;
  factory_id: number;
  sku: string;
  name: string;
  description?: string | null;
  fiber_composition?: string | null;
  garment_weight_g: number;
  cutting_waste_percent: number;
  recycled_content_pct: number;
  care_instructions?: string | null;
  target_buyer?: string | null;
  active: boolean;
  created_at: string;
  bom_items: BomItem[];
}

export interface BomItemFormData {
  material_name: string;
  category: MaterialCategory;
  material_key?: string;
  quantity_per_garment_g: number;
  carbon_factor_override?: number | null;
  notes?: string;
}

export interface ProductFormData {
  sku: string;
  name: string;
  description?: string;
  fiber_composition?: string;
  garment_weight_g: number;
  cutting_waste_percent: number;
  recycled_content_pct: number;
  care_instructions?: string;
  target_buyer?: string;
  active: boolean;
  bom: BomItemFormData[];
}

export interface ProductCarbonBreakdown {
  material_name: string;
  category: MaterialCategory;
  quantity_per_garment_g: number;
  carbon_factor: number;
  emissions_per_garment_kg: number;
}

export interface ProductCarbon {
  product_id: number;
  sku: string;
  name: string;
  total_per_garment_kg: number;
  breakdown: ProductCarbonBreakdown[];
  actual_per_garment_kg: number | null;
  batches_observed: number;
}

// ---------------------------------------------------------------------------
// Phase 2 — production batches & allocation
// ---------------------------------------------------------------------------

export type ProcessType =
  | 'knitting'
  | 'bleaching'
  | 'dyeing'
  | 'printing'
  | 'finishing'
  | 'cutting_sewing';
export type AllocationMethod = 'mass' | 'units' | 'economic';
export type DataQuality = 'measured' | 'estimated' | 'default_factor';
export type BatchInputType =
  | 'water_l'
  | 'electricity_kwh'
  | 'chemical_kg'
  | 'dye_kg'
  | 'steam_kg'
  | 'diesel_l';
export type OrderStatus = 'open' | 'in_production' | 'completed' | 'cancelled';
export type InventoryStatus = 'in_stock' | 'consumed' | 'sold' | 'waste';

export interface Order {
  id: number;
  factory_id: number;
  order_code: string;
  buyer_name?: string | null;
  product_id: number;
  units: number;
  order_value?: number | null;
  status: OrderStatus;
  share_token?: string | null;
  notes?: string | null;
  created_at: string;
  fabric_demand_kg?: number | null;
}

export interface OrderFormData {
  order_code: string;
  buyer_name?: string;
  product_id: number;
  units: number;
  order_value?: number | null;
  status: OrderStatus;
  notes?: string;
}

export interface BatchInput {
  id: number;
  batch_id: number;
  input_type: BatchInputType;
  chemical_id?: number | null;
  quantity: number;
  data_quality: DataQuality;
  source?: string | null;
}

export interface BatchInputFormData {
  input_type: BatchInputType;
  chemical_id?: number | null;
  quantity: number;
  data_quality: DataQuality;
  source?: string;
}

export interface BatchAllocation {
  id: number;
  batch_id: number;
  order_id: number;
  product_id?: number | null;
  fabric_kg: number;
  garment_units?: number | null;
  order_value?: number | null;
  allocated_share: number;
}

export interface ProductionBatch {
  id: number;
  factory_id: number;
  batch_code: string;
  process_type: ProcessType;
  colour?: string | null;
  started_at: string;
  completed_at?: string | null;
  total_fabric_kg: number;
  is_rework: boolean;
  rework_of_batch_id?: number | null;
  allocation_method: AllocationMethod;
  allocation_note?: string | null;
  outsourced: boolean;
  job_worker_id?: number | null;
  job_work_token?: string | null;
  created_at: string;
  inputs: BatchInput[];
  allocations: BatchAllocation[];
}

export interface BatchFormData {
  batch_code: string;
  process_type: ProcessType;
  colour?: string;
  started_at: string;
  total_fabric_kg: number;
  is_rework: boolean;
  rework_of_batch_id?: number | null;
  allocation_method: AllocationMethod;
  allocation_note?: string;
  outsourced: boolean;
  job_worker_id?: number | null;
  inputs: BatchInputFormData[];
}

export interface BatchLine {
  batch_id: number;
  batch_code: string;
  process_type: string;
  allocation_method: string;
  allocated_share: number;
  co2_kg: number;
  water_l: number;
  is_rework: boolean;
  outsourced: boolean;
  data_quality_flags: string[];
  allocation_note?: string | null;
}

export interface OrderFootprint {
  order_id: number;
  order_code: string;
  buyer_name?: string | null;
  product_sku?: string | null;
  product_name?: string | null;
  units: number;
  co2_kg: number;
  co2_per_garment_kg: number;
  water_l: number;
  water_per_garment_l: number;
  batch_lines: BatchLine[];
  embodied_co2_kg: number;
  embodied_water_l: number;
  overhead_co2_kg: number;
  overhead_water_l: number;
  quality_mix: Record<DataQuality, number>;
  used_economic_allocation: boolean;
}

export interface JobWorker {
  id: number;
  factory_id: number;
  name: string;
  process_type: ProcessType;
  location?: string | null;
  contact?: string | null;
  created_at: string;
}

export interface FabricInventoryItem {
  id: number;
  factory_id: number;
  source_batch_id: number;
  fabric_kg: number;
  embodied_co2_kg: number;
  embodied_water_l: number;
  status: InventoryStatus;
  consumed_by_order_id?: number | null;
  created_at: string;
}

export interface MonthlyUtility {
  id: number;
  factory_id: number;
  year: number;
  month: number;
  total_electricity_kwh: number;
  total_water_liters: number;
  note?: string | null;
  created_at: string;
}

export interface BatchOverhead {
  batch_code: string;
  fabric_kg: number;
  overhead_kwh: number;
  overhead_water_l: number;
}

export interface Reconciliation {
  year: number;
  month: number;
  total_electricity_kwh: number;
  total_water_liters: number;
  attributed_kwh: number;
  attributed_water_l: number;
  overhead_kwh: number;
  overhead_water_l: number;
  total_fabric_kg: number;
  per_batch: Record<string, BatchOverhead>;
}

export interface JobWorkInfo {
  batch_code: string;
  process_type: string;
  colour?: string | null;
  total_fabric_kg: number;
  factory_name?: string | null;
  already_submitted: boolean;
}

// Audit Log types
export interface AuditLog {
  id: number;
  factory_id: number;
  user_id: number;
  action: string;
  entity_type: string;
  entity_id: number;
  old_value?: Record<string, unknown>;
  new_value?: Record<string, unknown>;
  timestamp: string;
}
