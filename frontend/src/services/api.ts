import axios from 'axios';
import type {
  AuthResponse,
  LoginCredentials,
  RegisterData,
  User,
  Factory,
  FactoryFormData,
  ProductionRecord,
  ProductionFormData,
  Chemical,
  ChemicalFormData,
  CarbonSummary,
  WaterEnergyTrends,
  Report,
  ReportFormData,
  DashboardSummary,
  AuditLog,
  Product,
  ProductFormData,
  ProductCarbon,
  Order,
  OrderFormData,
  OrderFootprint,
  ProductionBatch,
  BatchFormData,
  BatchInput,
  BatchInputFormData,
  JobWorker,
  JobWorkInfo,
  FabricInventoryItem,
  MonthlyUtility,
  Reconciliation,
  ProcessType,
  InventoryStatus,
  Boundary,
  LifecycleFootprint,
  LifecycleSettings,
  PassportStatus,
  ProductSupplierLink,
  PublicPassport,
  ScenarioRequest,
  ScenarioResult,
  Supplier,
  SupplierDataRequest,
  SupplierFormData,
  SupplierRequestInfo,
  SupplierSubmission,
  SupplierSubmissionFormData,
  SupplyChainStage,
  ValidationResult,
} from '@/types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Create axios instance
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  register: (data: RegisterData) =>
    api.post<User>('/auth/register', data).then((res) => res.data),

  login: (credentials: LoginCredentials) =>
    api.post<AuthResponse>('/auth/login', credentials).then((res) => res.data),

  getMe: () => api.get<User>('/auth/me').then((res) => res.data),
};

// Factory API
export const factoryAPI = {
  get: () => api.get<Factory>('/factory').then((res) => res.data),

  create: (data: FactoryFormData) =>
    api.post<Factory>('/factory', data).then((res) => res.data),

  update: (data: FactoryFormData) =>
    api.put<Factory>('/factory', data).then((res) => res.data),
};

// Production API
export const productionAPI = {
  getAll: (params?: { month?: number; year?: number }) =>
    api.get<ProductionRecord[]>('/production', { params }).then((res) => res.data),

  create: (data: ProductionFormData) =>
    api.post<ProductionRecord>('/production', data).then((res) => res.data),

  update: (id: number, data: ProductionFormData) =>
    api.put<ProductionRecord>(`/production/${id}`, data).then((res) => res.data),

  delete: (id: number) => api.delete(`/production/${id}`).then((res) => res.data),
};

// Carbon API
export const carbonAPI = {
  getSummary: (dateFrom: string, dateTo: string) =>
    api
      .get<CarbonSummary>('/carbon/summary', {
        params: { date_from: dateFrom, date_to: dateTo },
      })
      .then((res) => res.data),

  getBreakdown: (dateFrom: string, dateTo: string) =>
    api
      .get<CarbonSummary>('/carbon/breakdown', {
        params: { date_from: dateFrom, date_to: dateTo },
      })
      .then((res) => res.data),
};

// Water & Energy API
export const waterEnergyAPI = {
  getTrends: (months: number = 6) =>
    api
      .get<WaterEnergyTrends>('/water-energy/trends', { params: { months } })
      .then((res) => res.data),
};

// Chemicals API
export const chemicalsAPI = {
  getAll: () => api.get<Chemical[]>('/chemicals').then((res) => res.data),

  create: (data: ChemicalFormData) =>
    api.post<Chemical>('/chemicals', data).then((res) => res.data),

  update: (id: number, data: ChemicalFormData) =>
    api.put<Chemical>(`/chemicals/${id}`, data).then((res) => res.data),

  delete: (id: number) => api.delete(`/chemicals/${id}`).then((res) => res.data),

  checkCompliance: (casNumber: string) =>
    api
      .get<{ cas_number: string; is_restricted: boolean; recommendation: string }>(
        `/chemicals/compliance-check/${casNumber}`
      )
      .then((res) => res.data),
};

// Reports API
export const reportsAPI = {
  getAll: () => api.get<Report[]>('/reports').then((res) => res.data),

  generate: (data: ReportFormData) =>
    api.post<Report>('/reports/generate', data).then((res) => res.data),

  download: (id: number) => {
    return api
      .get(`/reports/${id}/download`, { responseType: 'blob' })
      .then((response) => {
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `sustainability_report_${id}.pdf`);
        document.body.appendChild(link);
        link.click();
        link.remove();
      });
  },
};

// Dashboard API
export const dashboardAPI = {
  getSummary: () => api.get<DashboardSummary>('/dashboard/summary').then((res) => res.data),
};

// OCR API — assist-only extraction from utility bills / invoices.
// Returns structured fields for the user to confirm before saving.
export type OcrHint = 'electricity_bill' | 'water_bill' | 'dye_invoice' | 'fabric_invoice';

export interface OcrResponse {
  hint: OcrHint;
  filename: string;
  content_type: string;
  size_bytes: number;
  fields: Record<string, unknown>;
  confidence: number;
  notes: string;
  raw_model_text: string;
}

export const ocrAPI = {
  extract: (file: File, hint: OcrHint) => {
    const form = new FormData();
    form.append('file', file);
    form.append('hint', hint);
    return api
      .post<OcrResponse>('/ocr/extract', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60_000, // vision calls can take 10-30s
      })
      .then((res) => res.data);
  },
};

// Products API — per-SKU catalog with bills of materials. Per-garment carbon
// is a function of the BOM, so the carbon endpoint is per-product, not a
// rollup of the whole factory.
export const productsAPI = {
  getAll: () => api.get<Product[]>('/products').then((res) => res.data),

  get: (id: number) => api.get<Product>(`/products/${id}`).then((res) => res.data),

  create: (data: ProductFormData) =>
    api.post<Product>('/products', data).then((res) => res.data),

  update: (id: number, data: Omit<ProductFormData, 'bom'>) =>
    api.put<Product>(`/products/${id}`, data).then((res) => res.data),

  delete: (id: number) => api.delete(`/products/${id}`).then((res) => res.data),

  getCarbon: (id: number) =>
    api.get<ProductCarbon>(`/products/${id}/carbon`).then((res) => res.data),
};

// ---------------------------------------------------------------------------
// Phase 2 — batches, orders, allocation
// ---------------------------------------------------------------------------

// Orders API — the unit footprints are reported against.
export const ordersAPI = {
  getAll: (status?: string) =>
    api
      .get<Order[]>('/orders', { params: status ? { status_filter: status } : undefined })
      .then((res) => res.data),

  create: (data: OrderFormData) =>
    api.post<Order>('/orders', data).then((res) => res.data),

  update: (id: number, data: OrderFormData) =>
    api.put<Order>(`/orders/${id}`, data).then((res) => res.data),

  delete: (id: number) => api.delete(`/orders/${id}`).then((res) => res.data),

  getFootprint: (id: number) =>
    api.get<OrderFootprint>(`/orders/${id}/footprint`).then((res) => res.data),

  createShareLink: (id: number) =>
    api.post<Order>(`/orders/${id}/share-link`).then((res) => res.data),
};

// Production Batches API — the primary data-entry unit.
export const batchesAPI = {
  getAll: (processType?: ProcessType) =>
    api
      .get<ProductionBatch[]>('/batches', {
        params: processType ? { process_type: processType } : undefined,
      })
      .then((res) => res.data),

  get: (id: number) => api.get<ProductionBatch>(`/batches/${id}`).then((res) => res.data),

  create: (data: BatchFormData) =>
    api.post<ProductionBatch>('/batches', data).then((res) => res.data),

  delete: (id: number) => api.delete(`/batches/${id}`).then((res) => res.data),

  addInput: (batchId: number, data: BatchInputFormData) =>
    api.post<BatchInput>(`/batches/${batchId}/inputs`, data).then((res) => res.data),

  deleteInput: (batchId: number, inputId: number) =>
    api.delete(`/batches/${batchId}/inputs/${inputId}`).then((res) => res.data),

  attachOrders: (batchId: number, lines: { order_id: number; fabric_kg?: number | null }[]) =>
    api
      .post<ProductionBatch>(`/batches/${batchId}/allocations`, { lines })
      .then((res) => res.data),

  complete: (batchId: number) =>
    api.post<ProductionBatch>(`/batches/${batchId}/complete`).then((res) => res.data),

  createJobworkLink: (batchId: number) =>
    api.post<ProductionBatch>(`/batches/${batchId}/jobwork-link`).then((res) => res.data),
};

// Job workers (outsourced dyeing units, CETPs).
export const jobWorkersAPI = {
  getAll: () => api.get<JobWorker[]>('/job-workers').then((res) => res.data),

  create: (data: { name: string; process_type: ProcessType; location?: string; contact?: string }) =>
    api.post<JobWorker>('/job-workers', data).then((res) => res.data),
};

// Public (login-free) endpoints: job-work submission + buyer share view.
// Plain axios instance — no auth token, no 401 redirect.
const publicApi = axios.create({ baseURL: API_URL });

export const publicAPI = {
  getJobWorkInfo: (token: string) =>
    publicApi.get<JobWorkInfo>(`/jobwork/${token}`).then((res) => res.data),

  submitJobWork: (token: string, inputs: BatchInputFormData[], submittedBy?: string) =>
    publicApi
      .post(`/jobwork/${token}`, { inputs, submitted_by: submittedBy })
      .then((res) => res.data),

  getSharedFootprint: (token: string) =>
    publicApi.get<OrderFootprint>(`/share/${token}`).then((res) => res.data),

  getPassport: (token: string, version?: number) =>
    publicApi
      .get<PublicPassport>(`/passport/${token}`, { params: version ? { version } : undefined })
      .then((res) => res.data),

  passportQrUrl: (token: string) => `${API_URL}/passport/${token}/qr.svg`,

  getSupplierRequest: (token: string) =>
    publicApi.get<SupplierRequestInfo>(`/supplier-data/${token}`).then((res) => res.data),

  submitSupplierData: (token: string, data: SupplierSubmissionFormData) =>
    publicApi.post(`/supplier-data/${token}`, data).then((res) => res.data),
};

// Suppliers — the upstream supply chain map.
export const suppliersAPI = {
  getAll: () => api.get<Supplier[]>('/suppliers').then((res) => res.data),

  create: (data: SupplierFormData) =>
    api.post<Supplier>('/suppliers', data).then((res) => res.data),

  update: (id: number, data: SupplierFormData) =>
    api.put<Supplier>(`/suppliers/${id}`, data).then((res) => res.data),

  delete: (id: number) => api.delete(`/suppliers/${id}`).then((res) => res.data),

  createDataRequest: (id: number, data: { stage?: SupplyChainStage; period_label?: string }) =>
    api.post<SupplierDataRequest>(`/suppliers/${id}/data-requests`, data).then((res) => res.data),

  getDataRequests: (id: number) =>
    api.get<SupplierDataRequest[]>(`/suppliers/${id}/data-requests`).then((res) => res.data),

  getSubmissions: (id: number) =>
    api.get<SupplierSubmission[]>(`/suppliers/${id}/submissions`).then((res) => res.data),
};

// Product life cycle, validation, supply-chain links and passports.
export const lifecycleAPI = {
  getFootprint: (productId: number, boundary?: Boundary) =>
    api
      .get<LifecycleFootprint>(`/products/${productId}/footprint`, {
        params: boundary ? { boundary } : undefined,
      })
      .then((res) => res.data),

  runScenario: (productId: number, scenario: ScenarioRequest) =>
    api
      .post<ScenarioResult>(`/products/${productId}/footprint/scenario`, scenario)
      .then((res) => res.data),

  getSettings: (productId: number) =>
    api.get<LifecycleSettings>(`/products/${productId}/lifecycle`).then((res) => res.data),

  saveSettings: (productId: number, data: LifecycleSettings) =>
    api.put<LifecycleSettings>(`/products/${productId}/lifecycle`, data).then((res) => res.data),

  validate: (productId: number) =>
    api.get<ValidationResult>(`/products/${productId}/validation`).then((res) => res.data),

  getSuppliers: (productId: number) =>
    api.get<ProductSupplierLink[]>(`/products/${productId}/suppliers`).then((res) => res.data),

  linkSupplier: (productId: number, stage: SupplyChainStage, supplierId: number) =>
    api
      .put<ProductSupplierLink>(`/products/${productId}/suppliers`, {
        stage,
        supplier_id: supplierId,
      })
      .then((res) => res.data),

  unlinkSupplier: (productId: number, stage: SupplyChainStage) =>
    api.delete(`/products/${productId}/suppliers/${stage}`).then((res) => res.data),

  getPassport: (productId: number) =>
    api.get<PassportStatus>(`/products/${productId}/passport`).then((res) => res.data),

  publishPassport: (
    productId: number,
    data: { reviewed_by_name: string; review_note?: string; disclose_supplier_names: boolean }
  ) =>
    api
      .post<PassportStatus>(`/products/${productId}/passport/publish`, data)
      .then((res) => res.data),
};

// Fabric inventory (leftover / buffer fabric with embodied footprint).
export const inventoryAPI = {
  getAll: (status?: InventoryStatus) =>
    api
      .get<FabricInventoryItem[]>('/inventory', {
        params: status ? { status_filter: status } : undefined,
      })
      .then((res) => res.data),

  consume: (id: number, orderId: number) =>
    api
      .post<FabricInventoryItem>(`/inventory/${id}/consume`, { order_id: orderId })
      .then((res) => res.data),

  writeOff: (id: number, status: 'sold' | 'waste') =>
    api
      .post<FabricInventoryItem>(`/inventory/${id}/write-off`, { status })
      .then((res) => res.data),
};

// Monthly utilities + single-meter reconciliation.
export const utilitiesAPI = {
  getAll: () => api.get<MonthlyUtility[]>('/utilities').then((res) => res.data),

  upsert: (data: {
    year: number;
    month: number;
    total_electricity_kwh: number;
    total_water_liters: number;
    note?: string;
  }) => api.post<MonthlyUtility>('/utilities', data).then((res) => res.data),

  reconcile: (year: number, month: number) =>
    api.get<Reconciliation>(`/utilities/reconcile/${year}/${month}`).then((res) => res.data),
};

// Audit Log API
export const auditLogAPI = {
  getAll: (params?: { entity_type?: string; date_from?: string; date_to?: string; limit?: number }) =>
    api.get<AuditLog[]>('/audit-log', { params }).then((res) => res.data),
};

export default api;
