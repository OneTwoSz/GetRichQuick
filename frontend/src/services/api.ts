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

// Audit Log API
export const auditLogAPI = {
  getAll: (params?: { entity_type?: string; date_from?: string; date_to?: string; limit?: number }) =>
    api.get<AuditLog[]>('/audit-log', { params }).then((res) => res.data),
};

export default api;
