import type { Boundary, StageDataSource, SupplyChainStage } from '@/types';

// Shared vocabulary for the Phase 3 life-cycle, supply-chain and passport UI.

export const SUPPLY_STAGE_LABELS: Record<SupplyChainStage, string> = {
  raw_materials: 'Raw materials (fibre)',
  yarn_production: 'Yarn (spinning)',
  fabric_production: 'Fabric (knitting)',
  wet_processing: 'Wet processing (dyeing)',
  assembly: 'Assembly (cut & sew)',
  trims_packaging: 'Trims & packaging',
};

export const SUPPLY_STAGES = Object.keys(SUPPLY_STAGE_LABELS) as SupplyChainStage[];

export const BOUNDARY_LABELS: Record<Boundary, string> = {
  cradle_to_gate: 'Cradle to gate',
  cradle_to_customer: 'Cradle to customer',
  cradle_to_grave: 'Cradle to grave',
};

export const SOURCE_LABELS: Record<StageDataSource, string> = {
  factory_primary: 'Factory primary data',
  factory_default: 'Factory batches (default factors)',
  supplier_primary: 'Supplier primary data',
  supplier_declared: 'Supplier-declared factor',
  default: 'Default factor',
  mixed: 'Mixed sources',
  none: '—',
};

// Bar / badge colours by data source: greens for primary data, amber for
// declared values, grey for defaults.
export const SOURCE_COLORS: Record<StageDataSource, { bar: string; badge: string }> = {
  factory_primary: { bar: 'bg-green-600', badge: 'bg-green-100 text-green-800' },
  supplier_primary: { bar: 'bg-green-400', badge: 'bg-green-50 text-green-700' },
  supplier_declared: { bar: 'bg-amber-400', badge: 'bg-amber-100 text-amber-800' },
  factory_default: { bar: 'bg-gray-400', badge: 'bg-gray-100 text-gray-700' },
  default: { bar: 'bg-gray-300', badge: 'bg-gray-100 text-gray-600' },
  mixed: { bar: 'bg-teal-400', badge: 'bg-teal-50 text-teal-700' },
  none: { bar: 'bg-gray-200', badge: 'bg-gray-50 text-gray-500' },
};

export const QUALITY_COLORS: Record<string, string> = {
  measured: 'bg-green-500',
  estimated: 'bg-amber-400',
  default_factor: 'bg-gray-400',
};

export const QUALITY_LABELS: Record<string, string> = {
  measured: 'Measured',
  estimated: 'Estimated',
  default_factor: 'Default factor',
};

// Keys the backend factor library knows (utils/factor_library.py).
export const FIBRE_KEYS = [
  'cotton', 'organic_cotton', 'recycled_cotton', 'polyester', 'recycled_polyester',
  'elastane', 'nylon', 'recycled_nylon', 'viscose', 'lyocell', 'linen', 'wool', 'blend',
];

export const PACKAGING_KEYS = ['ldpe_polybag', 'recycled_ldpe_polybag', 'cardboard', 'paper'];

export const COUNTRIES: Record<string, string> = {
  IN: 'India', BD: 'Bangladesh', CN: 'China', VN: 'Vietnam', PK: 'Pakistan',
  LK: 'Sri Lanka', ID: 'Indonesia', TR: 'Türkiye', KH: 'Cambodia', EG: 'Egypt',
  PT: 'Portugal', IT: 'Italy', DE: 'Germany', FR: 'France', GB: 'United Kingdom',
  US: 'United States', EU: 'EU average',
};

export const humanize = (key: string) => key.replace(/_/g, ' ');
