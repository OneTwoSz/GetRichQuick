import { useEffect, useState, FormEvent } from 'react';
import { useParams } from 'react-router-dom';
import { publicAPI } from '@/services/api';
import type { BatchInputFormData, BatchInputType, JobWorkInfo } from '@/types';

// Login-free single form for a job worker (dyeing unit / CETP) to submit
// actual consumption for an outsourced batch. Mobile-first — this gets
// opened from a WhatsApp link on the shop floor.

const INPUT_LABELS: Record<BatchInputType, string> = {
  water_l: 'Water (litres)',
  electricity_kwh: 'Electricity (kWh)',
  chemical_kg: 'Chemicals (kg)',
  dye_kg: 'Dyes (kg)',
  steam_kg: 'Steam (kg)',
  diesel_l: 'Diesel (litres)',
};

const EMPTY_ROW: BatchInputFormData = {
  input_type: 'water_l',
  quantity: 0,
  data_quality: 'measured',
};

export default function JobWork() {
  const { token } = useParams<{ token: string }>();
  const [info, setInfo] = useState<JobWorkInfo | null>(null);
  const [rows, setRows] = useState<BatchInputFormData[]>([{ ...EMPTY_ROW }]);
  const [submittedBy, setSubmittedBy] = useState('');
  const [state, setState] = useState<'loading' | 'form' | 'done' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    publicAPI
      .getJobWorkInfo(token)
      .then((data) => {
        setInfo(data);
        setState('form');
      })
      .catch(() => setState('error'));
  }, [token]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    const inputs = rows.filter((r) => r.quantity > 0);
    if (!inputs.length) {
      setError('Enter at least one quantity.');
      return;
    }
    try {
      await publicAPI.submitJobWork(token, inputs, submittedBy.trim() || undefined);
      setState('done');
    } catch {
      setError('Submission failed — please try again.');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-6">
      <div className="max-w-md mx-auto space-y-4">
        <h1 className="text-xl font-bold text-primary text-center">GreenThread</h1>

        {state === 'loading' && <div className="text-center text-gray-500">Loading…</div>}
        {state === 'error' && (
          <div className="bg-white rounded-lg shadow p-6 text-sm text-red-600 text-center">
            This link is invalid or has expired. Ask the factory to send a new one.
          </div>
        )}
        {state === 'done' && (
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <div className="text-3xl mb-2">✓</div>
            <p className="font-semibold">Thank you!</p>
            <p className="text-sm text-gray-600">Your consumption figures were recorded.</p>
          </div>
        )}

        {state === 'form' && info && (
          <form onSubmit={submit} className="bg-white rounded-lg shadow p-4 space-y-4">
            <div>
              <p className="text-sm text-gray-600">
                <strong>{info.factory_name ?? 'A GreenThread factory'}</strong> requests actual
                consumption for:
              </p>
              <p className="font-mono font-semibold mt-1">{info.batch_code}</p>
              <p className="text-sm text-gray-600">
                {info.process_type}
                {info.colour ? ` · ${info.colour}` : ''} · {info.total_fabric_kg} kg fabric
              </p>
              {info.already_submitted && (
                <p className="text-xs text-amber-700 bg-amber-50 rounded p-2 mt-2">
                  Figures were already submitted for this lot — submitting again adds to them.
                </p>
              )}
            </div>

            {rows.map((row, idx) => (
              <div key={idx} className="flex gap-2">
                <select
                  className="input flex-1"
                  value={row.input_type}
                  onChange={(e) => {
                    const next = [...rows];
                    next[idx] = { ...row, input_type: e.target.value as BatchInputType };
                    setRows(next);
                  }}
                >
                  {Object.entries(INPUT_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
                <input
                  type="number"
                  inputMode="decimal"
                  step="0.01"
                  min="0"
                  className="input !w-28"
                  placeholder="Qty"
                  value={row.quantity || ''}
                  onChange={(e) => {
                    const next = [...rows];
                    next[idx] = { ...row, quantity: parseFloat(e.target.value) || 0 };
                    setRows(next);
                  }}
                />
              </div>
            ))}
            <button
              type="button"
              className="text-sm text-primary font-medium"
              onClick={() => setRows((prev) => [...prev, { ...EMPTY_ROW }])}
            >
              + Add another
            </button>

            <input
              className="input"
              placeholder="Your name (optional)"
              value={submittedBy}
              onChange={(e) => setSubmittedBy(e.target.value)}
            />

            {error && <div className="text-sm text-red-600">{error}</div>}

            <button className="w-full bg-primary text-white py-3 rounded-lg font-semibold">
              Submit consumption
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
