import { FormEvent, useEffect, useState } from 'react';
import { suppliersAPI } from '@/services/api';
import type { Supplier, SupplierFormData, SupplierSubmission, SupplyChainStage } from '@/types';
import { COUNTRIES, SUPPLY_STAGES, SUPPLY_STAGE_LABELS } from '@/components/lifecycleLabels';

// Upstream supply chain: Tier 2–4 facilities with location and
// certifications, their data submissions, and login-free request links.

const EMPTY: SupplierFormData = {
  name: '',
  stage: 'yarn_production',
  country: 'IN',
  city: '',
  certifications: [],
  contact: '',
};

export default function Suppliers() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<SupplierFormData>(EMPTY);
  const [certText, setCertText] = useState('');
  const [openId, setOpenId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    suppliersAPI
      .getAll()
      .then(setSuppliers)
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await suppliersAPI.create({
        ...form,
        city: form.city?.trim() || undefined,
        contact: form.contact?.trim() || undefined,
        certifications: certText
          .split(',')
          .map((c) => c.trim())
          .filter(Boolean)
          .map((name) => ({ name })),
      });
      setForm(EMPTY);
      setCertText('');
      setShowForm(false);
      load();
    } catch {
      setError('Could not save the supplier.');
    }
  };

  const remove = async (s: Supplier) => {
    if (!confirm(`Remove ${s.name}?`)) return;
    try {
      await suppliersAPI.delete(s.id);
      load();
    } catch {
      alert('This supplier is linked to products — unlink it on the product first.');
    }
  };

  const byTier = [4, 3, 2, 1]
    .map((tier) => ({ tier, rows: suppliers.filter((s) => s.tier === tier) }))
    .filter((g) => g.rows.length > 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-gray-900 sm:text-[28px]">Suppliers</h1>
          <p className="text-sm text-gray-600">
            Your upstream supply chain — fibre to fabric. Link them to products to trace each stage.
          </p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="shrink-0 whitespace-nowrap bg-primary text-white px-4 py-2 rounded-lg font-medium hover:bg-primary/90"
        >
          {showForm ? 'Cancel' : '+ Add supplier'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={save} className="bg-white rounded-lg shadow p-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Facility name *</span>
            <input
              className="input mt-1"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Stage *</span>
            <select
              className="input mt-1"
              value={form.stage}
              onChange={(e) => setForm({ ...form, stage: e.target.value as SupplyChainStage })}
            >
              {SUPPLY_STAGES.filter((s) => s !== 'assembly').map((s) => (
                <option key={s} value={s}>{SUPPLY_STAGE_LABELS[s]}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Country *</span>
            <select
              className="input mt-1"
              value={form.country}
              onChange={(e) => setForm({ ...form, country: e.target.value })}
            >
              {Object.entries(COUNTRIES)
                .filter(([k]) => k !== 'EU')
                .map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="font-medium text-gray-700">City</span>
            <input
              className="input mt-1"
              value={form.city}
              onChange={(e) => setForm({ ...form, city: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Certifications</span>
            <input
              className="input mt-1"
              placeholder="GOTS, OEKO-TEX, GRS"
              value={certText}
              onChange={(e) => setCertText(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium text-gray-700">Contact</span>
            <input
              className="input mt-1"
              placeholder="Phone or email"
              value={form.contact}
              onChange={(e) => setForm({ ...form, contact: e.target.value })}
            />
          </label>
          {error && <div className="text-sm text-red-600 sm:col-span-2">{error}</div>}
          <div className="sm:col-span-2">
            <button className="shrink-0 whitespace-nowrap bg-primary text-white px-4 py-2 rounded-lg font-medium hover:bg-primary/90">
              Save supplier
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-gray-500">Loading…</div>
      ) : suppliers.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No suppliers yet. Add your spinner, knit mill or dye house to start tracing.
        </div>
      ) : (
        byTier.map(({ tier, rows }) => (
          <div key={tier}>
            <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">
              Tier {tier}
            </h2>
            <div className="bg-white rounded-lg shadow divide-y">
              {rows.map((s) => (
                <SupplierRow
                  key={s.id}
                  supplier={s}
                  open={openId === s.id}
                  onToggle={() => setOpenId(openId === s.id ? null : s.id)}
                  onRemove={() => remove(s)}
                />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function SupplierRow({
  supplier,
  open,
  onToggle,
  onRemove,
}: {
  supplier: Supplier;
  open: boolean;
  onToggle: () => void;
  onRemove: () => void;
}) {
  const [subs, setSubs] = useState<SupplierSubmission[] | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const [period, setPeriod] = useState('');

  useEffect(() => {
    if (open && subs === null) suppliersAPI.getSubmissions(supplier.id).then(setSubs);
  }, [open, subs, supplier.id]);

  const makeLink = async () => {
    const req = await suppliersAPI.createDataRequest(supplier.id, {
      period_label: period.trim() || undefined,
    });
    setLink(`${window.location.origin}/supplier-data/${req.token}`);
  };

  const collectsData = !['raw_materials', 'trims_packaging'].includes(supplier.stage);

  return (
    <div className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button onClick={onToggle} className="text-left">
          <div className="font-semibold">{supplier.name}</div>
          <div className="text-xs text-gray-600">
            {SUPPLY_STAGE_LABELS[supplier.stage]} · {supplier.city ? `${supplier.city}, ` : ''}
            {COUNTRIES[supplier.country] ?? supplier.country}
          </div>
        </button>
        <div className="flex flex-wrap items-center gap-2">
          {supplier.certifications.map((c) => (
            <span key={c.name} className="text-xs px-2 py-0.5 rounded bg-green-50 text-green-700">
              {c.name}
            </span>
          ))}
          <button onClick={onToggle} className="text-sm text-primary">
            {open ? 'Close' : 'Data'}
          </button>
        </div>
      </div>

      {open && (
        <div className="mt-3 space-y-3 text-sm">
          {collectsData && (
            <div className="flex flex-wrap gap-2 items-center">
              <input
                className="input !w-48"
                placeholder="Period, e.g. Apr–Jun 2026"
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
              />
              <button onClick={makeLink} className="bg-primary text-white px-3 py-2 rounded-lg">
                Create data request link
              </button>
            </div>
          )}
          {link && (
            <div className="flex gap-2">
              <input readOnly className="input font-mono text-xs" value={link} />
              <button
                className="bg-gray-800 text-white px-3 rounded-lg"
                onClick={() => navigator.clipboard?.writeText(link)}
              >
                Copy
              </button>
            </div>
          )}
          {subs === null ? (
            <div className="text-gray-500">Loading submissions…</div>
          ) : subs.length === 0 ? (
            <div className="text-gray-500">
              {collectsData ? 'No data submitted yet — stages use default factors.' : 'No submissions.'}
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead className="text-gray-600 text-left border-b">
                <tr>
                  <th className="py-1">Period</th>
                  <th className="py-1 pr-4 text-right">Output kg</th>
                  <th className="py-1 pr-4 text-right">kWh/kg</th>
                  <th className="py-1 pr-4 text-right">Water L/kg</th>
                  <th className="py-1">Quality</th>
                  <th className="py-1">By</th>
                </tr>
              </thead>
              <tbody>
                {subs.map((s) => (
                  <tr key={s.id} className="border-b last:border-b-0">
                    <td className="py-1">{s.period_label ?? new Date(s.created_at).toLocaleDateString()}</td>
                    <td className="py-1 pr-4 text-right tabular-nums">{s.output_kg.toLocaleString()}</td>
                    <td className="py-1 pr-4 text-right tabular-nums">{(s.electricity_kwh / s.output_kg).toFixed(2)}</td>
                    <td className="py-1 pr-4 text-right tabular-nums">{(s.water_l / s.output_kg).toFixed(1)}</td>
                    <td className="py-1">{s.data_quality}</td>
                    <td className="py-1">{s.submitted_by ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <button onClick={onRemove} className="text-xs text-red-600">
            Remove supplier
          </button>
        </div>
      )}
    </div>
  );
}
