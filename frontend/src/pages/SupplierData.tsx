import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { publicAPI } from '@/services/api';
import type { SupplierRequestInfo, SupplierSubmissionFormData } from '@/types';
import { SUPPLY_STAGE_LABELS } from '@/components/lifecycleLabels';

// Login-free form for an upstream supplier (spinner, knit mill, dye house)
// to submit facility totals for a period. Mobile-first — opened from a
// WhatsApp link. Totals ÷ output become that stage's primary-data intensity.

const FIELDS: { key: keyof SupplierSubmissionFormData; label: string; hint: string }[] = [
  { key: 'electricity_kwh', label: 'Electricity (kWh)', hint: 'From the EB bill(s) for the period' },
  { key: 'water_l', label: 'Water (litres)', hint: 'Borewell / tanker / municipal' },
  { key: 'steam_kg', label: 'Steam (kg)', hint: 'Boiler output, if any' },
  { key: 'diesel_l', label: 'Diesel (litres)', hint: 'Generator fuel' },
  { key: 'chemical_kg', label: 'Chemicals (kg)', hint: 'Auxiliaries, salts, alkali' },
  { key: 'dye_kg', label: 'Dyes (kg)', hint: 'Dyestuff consumed' },
];

const EMPTY: SupplierSubmissionFormData = {
  output_kg: 0,
  electricity_kwh: 0,
  water_l: 0,
  steam_kg: 0,
  diesel_l: 0,
  chemical_kg: 0,
  dye_kg: 0,
  data_quality: 'estimated',
};

export default function SupplierData() {
  const { token } = useParams<{ token: string }>();
  const [info, setInfo] = useState<SupplierRequestInfo | null>(null);
  const [form, setForm] = useState<SupplierSubmissionFormData>(EMPTY);
  const [state, setState] = useState<'loading' | 'form' | 'done' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    publicAPI
      .getSupplierRequest(token)
      .then((data) => {
        setInfo(data);
        setForm((f) => ({ ...f, period_label: data.period_label ?? '' }));
        setState('form');
      })
      .catch(() => setState('error'));
  }, [token]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    if (form.output_kg <= 0) {
      setError('Enter how many kg you produced in the period.');
      return;
    }
    try {
      await publicAPI.submitSupplierData(token, {
        ...form,
        period_label: form.period_label?.trim() || undefined,
        submitted_by: form.submitted_by?.trim() || undefined,
      });
      setState('done');
    } catch {
      setError('Submission failed — please check the numbers and try again.');
    }
  };

  const num = (key: keyof SupplierSubmissionFormData) => (
    <input
      type="number"
      inputMode="decimal"
      min="0"
      step="any"
      className="input"
      value={(form[key] as number) || ''}
      onChange={(e) => setForm({ ...form, [key]: parseFloat(e.target.value) || 0 })}
    />
  );

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-6">
      <div className="max-w-md mx-auto space-y-4">
        <h1 className="text-xl font-bold text-primary text-center">GreenThread</h1>

        {state === 'loading' && <div className="text-center text-gray-500">Loading…</div>}
        {state === 'error' && (
          <div className="bg-white rounded-lg shadow p-6 text-sm text-red-600 text-center">
            This link is invalid. Ask your customer to send a new one.
          </div>
        )}
        {state === 'done' && (
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-3xl mb-2">✓</div>
            <p className="font-semibold">Thank you!</p>
            <p className="text-sm text-gray-600">
              Your figures were recorded. Your customer can now report your stage with real data.
            </p>
          </div>
        )}

        {state === 'form' && info && (
          <form onSubmit={submit} className="bg-white rounded-lg shadow p-4 space-y-4">
            <div>
              <p className="text-sm text-gray-600">
                <strong>{info.factory_name ?? 'Your customer'}</strong> requests facility data from{' '}
                <strong>{info.supplier_name}</strong> for:
              </p>
              <p className="font-semibold mt-1">{SUPPLY_STAGE_LABELS[info.stage]}</p>
              <p className="text-xs text-gray-500 mt-1">
                Enter totals for the whole facility over the period. Only per-kg averages are used —
                your volumes are not shown to anyone else.
              </p>
              {info.already_submitted && (
                <p className="text-xs text-amber-700 bg-amber-50 rounded p-2 mt-2">
                  Figures were already submitted on this link — a new submission replaces them.
                </p>
              )}
            </div>

            <label className="block text-sm">
              <span className="font-medium">Period</span>
              <input
                className="input mt-1"
                placeholder="e.g. Apr–Jun 2026"
                value={form.period_label ?? ''}
                onChange={(e) => setForm({ ...form, period_label: e.target.value })}
              />
            </label>

            <label className="block text-sm">
              <span className="font-medium">Total output in the period (kg) *</span>
              <div className="mt-1">{num('output_kg')}</div>
            </label>

            {FIELDS.map((f) => (
              <label key={f.key} className="block text-sm">
                <span className="font-medium">{f.label}</span>
                <span className="block text-xs text-gray-500">{f.hint}</span>
                <div className="mt-1">{num(f.key)}</div>
              </label>
            ))}

            <fieldset className="text-sm">
              <legend className="font-medium mb-1">These figures come from</legend>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  checked={form.data_quality === 'measured'}
                  onChange={() => setForm({ ...form, data_quality: 'measured' })}
                />
                Meter readings / weighed records
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  checked={form.data_quality === 'estimated'}
                  onChange={() => setForm({ ...form, data_quality: 'estimated' })}
                />
                Bills or estimates
              </label>
            </fieldset>

            <input
              className="input"
              placeholder="Your name (optional)"
              value={form.submitted_by ?? ''}
              onChange={(e) => setForm({ ...form, submitted_by: e.target.value })}
            />

            {error && <div className="text-sm text-red-600">{error}</div>}

            <button className="w-full bg-primary text-white py-3 rounded-lg font-semibold">
              Submit figures
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
