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
  alerts: DashboardAlert[];
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
