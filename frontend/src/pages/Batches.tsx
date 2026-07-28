import { useEffect, useMemo, useState, FormEvent } from 'react';
import { batchesAPI, jobWorkersAPI, ordersAPI } from '@/services/api';
import type {
  AllocationMethod,
  BatchFormData,
  BatchInputFormData,
  BatchInputType,
  DataQuality,
  JobWorker,
  Order,
  ProcessType,
  ProductionBatch,
} from '@/types';

// "New Batch" is the primary data-entry action of phase 2 — it mirrors how
// production actually runs: one lot, one dye bath, shared meters. Orders
// attach afterwards and the engine shows the split live.

const PROCESS_LABELS: Record<ProcessType, string> = {
  knitting: 'Knitting',
  bleaching: 'Bleaching',
  dyeing: 'Dyeing',
  printing: 'Printing',
  finishing: 'Finishing',
  cutting_sewing: 'Cutting & Sewing',
};

const INPUT_LABELS: Record<BatchInputType, string> = {
  water_l: 'Water (L)',
  electricity_kwh: 'Electricity (kWh)',
  chemical_kg: 'Chemicals (kg)',
  dye_kg: 'Dyes (kg)',
  steam_kg: 'Steam (kg)',
  diesel_l: 'Diesel (L)',
};

const QUALITY_LABELS: Record<DataQuality, string> = {
  measured: 'Measured',
  estimated: 'Estimated (from bill)',
  default_factor: 'Default factor',
};

const METHOD_LABELS: Record<AllocationMethod, string> = {
  mass: 'Mass (default)',
  units: 'Garment units',
  economic: 'Economic (fallback)',
};

const SHARE_COLORS = ['bg-teal-500', 'bg-sky-500', 'bg-amber-500', 'bg-violet-500', 'bg-rose-500'];

const EMPTY_INPUT: BatchInputFormData = {
  input_type: 'water_l',
  quantity: 0,
  data_quality: 'measured',
  source: '',
};

function emptyForm(): BatchFormData {
  return {
    batch_code: '',
    process_type: 'dyeing',
    colour: '',
    started_at: new Date().toISOString().slice(0, 10),
    total_fabric_kg: 0,
    is_rework: false,
    rework_of_batch_id: null,
    allocation_method: 'mass',
    allocation_note: '',
    outsourced: false,
    job_worker_id: null,
    inputs: [{ ...EMPTY_INPUT }],
  };
}

export default function Batches() {
  const [batches, setBatches] = useState<ProductionBatch[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [jobWorkers, setJobWorkers] = useState<JobWorker[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<BatchFormData>(emptyForm());
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selected = batches.find((b) => b.id === selectedId) ?? null;

  const reworkRate = useMemo(() => {
    if (!batches.length) return 0;
    return batches.filter((b) => b.is_rework).length / batches.length;
  }, [batches]);

  useEffect(() => {
    void loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [batchData, orderData, workerData] = await Promise.all([
        batchesAPI.getAll(),
        ordersAPI.getAll(),
        jobWorkersAPI.getAll(),
      ]);
      setBatches(batchData);
      setOrders(orderData);
      setJobWorkers(workerData);
    } catch (err) {
      console.error('Failed to load batches', err);
    } finally {
      setLoading(false);
    }
  };

  const refreshBatch = (updated: ProductionBatch) => {
    setBatches((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
  };

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const payload: BatchFormData = {
        ...formData,
        colour: formData.colour?.trim() || undefined,
        allocation_note: formData.allocation_note?.trim() || undefined,
        started_at: new Date(formData.started_at).toISOString(),
        rework_of_batch_id: formData.is_rework ? formData.rework_of_batch_id : null,
        job_worker_id: formData.outsourced ? formData.job_worker_id : null,
        inputs: formData.inputs
          .filter((i) => i.quantity > 0)
          .map((i) => ({ ...i, source: i.source?.trim() || undefined })),
      };
      const created = await batchesAPI.create(payload);
      setBatches((prev) => [created, ...prev]);
      setShowForm(false);
      setFormData(emptyForm());
      setSelectedId(created.id);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to create batch');
    }
  };

  const updateInputRow = (idx: number, patch: Partial<BatchInputFormData>) => {
    setFormData((prev) => {
      const next = [...prev.inputs];
      next[idx] = { ...next[idx], ...patch };
      return { ...prev, inputs: next };
    });
  };

  if (loading) {
    return <div className="text-gray-500">Loading batches…</div>;
  }

  return (
    <div className="space-y-6 pb-24 md:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">Production Batches</h2>
          <p className="text-sm text-gray-600">
            Log resources against the lot as it runs — orders attach afterwards.
          </p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="bg-primary text-white px-5 py-3 rounded-lg text-sm font-semibold shadow hover:opacity-90"
        >
          {showForm ? 'Close' : '+ New Batch'}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard label="Total batches" value={batches.length.toString()} />
        <SummaryCard
          label="Rework rate"
          value={`${(reworkRate * 100).toFixed(1)}%`}
          accent={reworkRate > 0.1 ? 'text-red-600' : 'text-green-700'}
        />
        <SummaryCard
          label="Outsourced lots"
          value={batches.filter((b) => b.outsourced).length.toString()}
        />
        <SummaryCard
          label="Open (not completed)"
          value={batches.filter((b) => !b.completed_at).length.toString()}
        />
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white rounded-lg shadow p-4 sm:p-6 space-y-4">
          <h3 className="font-semibold">New batch</h3>
          {error && <div className="text-sm text-red-600 bg-red-50 rounded p-2">{error}</div>}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <Field label="Batch code" required>
              <input
                className="input"
                placeholder="LOT-2026-0714-WHT"
                value={formData.batch_code}
                onChange={(e) => setFormData({ ...formData, batch_code: e.target.value })}
                required
              />
            </Field>
            <Field label="Process" required>
              <select
                className="input"
                value={formData.process_type}
                onChange={(e) =>
                  setFormData({ ...formData, process_type: e.target.value as ProcessType })
                }
              >
                {Object.entries(PROCESS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </Field>
            <Field label="Colour">
              <input
                className="input"
                placeholder="white"
                value={formData.colour ?? ''}
                onChange={(e) => setFormData({ ...formData, colour: e.target.value })}
              />
            </Field>
            <Field label="Total fabric (kg)" required>
              <input
                type="number"
                step="0.1"
                min="0.1"
                className="input"
                value={formData.total_fabric_kg || ''}
                onChange={(e) =>
                  setFormData({ ...formData, total_fabric_kg: parseFloat(e.target.value) || 0 })
                }
                required
              />
            </Field>
            <Field label="Started">
              <input
                type="date"
                className="input"
                value={formData.started_at.slice(0, 10)}
                onChange={(e) => setFormData({ ...formData, started_at: e.target.value })}
                required
              />
            </Field>
            <Field label="Allocation method">
              <select
                className="input"
                value={formData.allocation_method}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    allocation_method: e.target.value as AllocationMethod,
                  })
                }
              >
                {Object.entries(METHOD_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </Field>
          </div>

          <div className="flex flex-wrap gap-6">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={formData.is_rework}
                onChange={(e) => setFormData({ ...formData, is_rework: e.target.checked })}
              />
              Rework (re-dye / re-process of a failed lot)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={formData.outsourced}
                onChange={(e) => setFormData({ ...formData, outsourced: e.target.checked })}
              />
              Outsourced (job work)
            </label>
          </div>

          {formData.is_rework && (
            <Field label="Original (failed) batch" required>
              <select
                className="input"
                value={formData.rework_of_batch_id ?? ''}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    rework_of_batch_id: e.target.value ? Number(e.target.value) : null,
                  })
                }
                required
              >
                <option value="">Select batch…</option>
                {batches
                  .filter((b) => !b.is_rework)
                  .map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.batch_code} — {PROCESS_LABELS[b.process_type]}
                    </option>
                  ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Rework consumption is added to the original batch's orders pro rata — the
                footprint honestly reflects what happened.
              </p>
            </Field>
          )}

          {formData.outsourced && (
            <Field label="Job worker">
              <select
                className="input"
                value={formData.job_worker_id ?? ''}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    job_worker_id: e.target.value ? Number(e.target.value) : null,
                  })
                }
              >
                <option value="">Not on file</option>
                {jobWorkers.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name} ({PROCESS_LABELS[w.process_type]})
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Leave inputs empty to use built-in per-process defaults, or send the job worker a
                data request link after saving. Add job workers on this page's sidebar.
              </p>
            </Field>
          )}

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Meter readings / drawdowns</span>
              <button
                type="button"
                onClick={() =>
                  setFormData((prev) => ({ ...prev, inputs: [...prev.inputs, { ...EMPTY_INPUT }] }))
                }
                className="text-sm text-primary font-medium"
              >
                + Add input
              </button>
            </div>
            <div className="space-y-2">
              {formData.inputs.map((input, idx) => (
                <div key={idx} className="grid grid-cols-2 sm:grid-cols-4 gap-2 items-start">
                  <select
                    className="input"
                    value={input.input_type}
                    onChange={(e) =>
                      updateInputRow(idx, { input_type: e.target.value as BatchInputType })
                    }
                  >
                    {Object.entries(INPUT_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    className="input"
                    placeholder="Quantity"
                    value={input.quantity || ''}
                    onChange={(e) =>
                      updateInputRow(idx, { quantity: parseFloat(e.target.value) || 0 })
                    }
                  />
                  <select
                    className="input"
                    value={input.data_quality}
                    onChange={(e) =>
                      updateInputRow(idx, { data_quality: e.target.value as DataQuality })
                    }
                  >
                    {Object.entries(QUALITY_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                  <div className="flex gap-2">
                    <input
                      className="input"
                      placeholder="Source (meter, bill…)"
                      value={input.source ?? ''}
                      onChange={(e) => updateInputRow(idx, { source: e.target.value })}
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setFormData((prev) => ({
                          ...prev,
                          inputs: prev.inputs.filter((_, i) => i !== idx),
                        }))
                      }
                      className="text-red-500 text-sm px-1"
                      aria-label="Remove input"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <button
            type="submit"
            className="w-full sm:w-auto bg-primary text-white px-6 py-3 rounded-lg text-sm font-semibold"
          >
            Save batch
          </button>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="space-y-2">
          {batches.length === 0 && (
            <div className="text-sm text-gray-500 bg-white rounded-lg shadow p-4">
              No batches yet — “New Batch” is where data entry starts.
            </div>
          )}
          {batches.map((b) => (
            <button
              key={b.id}
              onClick={() => setSelectedId(b.id)}
              className={`w-full text-left rounded-lg border p-3 transition ${
                selectedId === b.id
                  ? 'border-primary bg-primary-50'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm font-semibold">{b.batch_code}</span>
                <span className="text-xs text-gray-500">{b.started_at.slice(0, 10)}</span>
              </div>
              <div className="text-xs text-gray-600 mt-1">
                {PROCESS_LABELS[b.process_type]}
                {b.colour ? ` · ${b.colour}` : ''} · {b.total_fabric_kg} kg
              </div>
              <div className="flex gap-1 mt-1 flex-wrap">
                {b.is_rework && <Chip color="red">rework</Chip>}
                {b.outsourced && <Chip color="amber">outsourced</Chip>}
                {b.completed_at ? <Chip color="green">completed</Chip> : <Chip color="gray">open</Chip>}
                {b.allocations.length > 0 && (
                  <Chip color="teal">{b.allocations.length} order(s)</Chip>
                )}
              </div>
            </button>
          ))}
        </div>

        <div className="lg:col-span-2">
          {selected ? (
            <BatchDetail
              batch={selected}
              orders={orders}
              onChanged={refreshBatch}
              onReload={loadAll}
            />
          ) : (
            <div className="text-sm text-gray-500 bg-white rounded-lg shadow p-6">
              Select a batch to log inputs, attach orders and see the live split.
            </div>
          )}
        </div>
      </div>

      <JobWorkerPanel jobWorkers={jobWorkers} onCreated={(w) => setJobWorkers((p) => [...p, w])} />
    </div>
  );
}

function BatchDetail({
  batch,
  orders,
  onChanged,
  onReload,
}: {
  batch: ProductionBatch;
  orders: Order[];
  onChanged: (b: ProductionBatch) => void;
  onReload: () => Promise<void>;
}) {
  const [attachLines, setAttachLines] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [newInput, setNewInput] = useState<BatchInputFormData>({ ...EMPTY_INPUT });

  useEffect(() => {
    // Seed the attach form with the current allocation set.
    const seed: Record<number, string> = {};
    for (const alloc of batch.allocations) seed[alloc.order_id] = String(alloc.fabric_kg);
    setAttachLines(seed);
    setError(null);
  }, [batch.id]);

  const openOrders = orders.filter(
    (o) => o.status === 'open' || o.status === 'in_production' || attachLines[o.id] !== undefined
  );

  // Live split preview — mass shares of what's currently ticked.
  const preview = useMemo(() => {
    const entries = Object.entries(attachLines)
      .map(([orderId, kg]) => ({ orderId: Number(orderId), kg: parseFloat(kg) || 0 }))
      .filter((e) => e.kg > 0);
    const claimed = entries.reduce((sum, e) => sum + e.kg, 0);
    return {
      entries,
      claimed,
      over: claimed > batch.total_fabric_kg + 1e-9,
      leftover: Math.max(batch.total_fabric_kg - claimed, 0),
    };
  }, [attachLines, batch.total_fabric_kg]);

  const toggleOrder = (order: Order) => {
    setAttachLines((prev) => {
      const next = { ...prev };
      if (next[order.id] !== undefined) {
        delete next[order.id];
      } else {
        next[order.id] = String(order.fabric_demand_kg ?? '');
      }
      return next;
    });
  };

  const saveAllocations = async () => {
    setBusy(true);
    setError(null);
    try {
      const lines = preview.entries.map((e) => ({ order_id: e.orderId, fabric_kg: e.kg }));
      const updated = await batchesAPI.attachOrders(batch.id, lines);
      onChanged(updated);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to save allocations');
    } finally {
      setBusy(false);
    }
  };

  const addInput = async () => {
    if (newInput.quantity <= 0) return;
    setBusy(true);
    setError(null);
    try {
      await batchesAPI.addInput(batch.id, {
        ...newInput,
        source: newInput.source?.trim() || undefined,
      });
      setNewInput({ ...EMPTY_INPUT });
      await onReload();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to add input');
    } finally {
      setBusy(false);
    }
  };

  const complete = async () => {
    setBusy(true);
    setError(null);
    try {
      const updated = await batchesAPI.complete(batch.id);
      onChanged(updated);
      if (preview.leftover > 0) {
        await onReload(); // inventory row was created
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to complete batch');
    } finally {
      setBusy(false);
    }
  };

  const mintJobworkLink = async () => {
    setBusy(true);
    try {
      const updated = await batchesAPI.createJobworkLink(batch.id);
      onChanged(updated);
      const url = `${window.location.origin}/jobwork/${updated.job_work_token}`;
      await navigator.clipboard.writeText(url).catch(() => undefined);
      alert(`Data request link copied:\n${url}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to create link');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-4 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="font-mono font-semibold">{batch.batch_code}</h3>
            <div className="text-sm text-gray-600">
              {PROCESS_LABELS[batch.process_type]}
              {batch.colour ? ` · ${batch.colour}` : ''} · {batch.total_fabric_kg} kg ·{' '}
              {METHOD_LABELS[batch.allocation_method]}
            </div>
          </div>
          <div className="flex gap-2">
            {batch.outsourced && (
              <button
                onClick={mintJobworkLink}
                disabled={busy}
                className="text-sm border border-primary text-primary px-3 py-2 rounded-lg font-medium"
              >
                {batch.job_work_token ? 'Copy data request link' : 'Create data request link'}
              </button>
            )}
            {!batch.completed_at && (
              <button
                onClick={complete}
                disabled={busy}
                className="text-sm bg-primary text-white px-3 py-2 rounded-lg font-medium"
              >
                Mark complete
              </button>
            )}
          </div>
        </div>
        {error && <div className="text-sm text-red-600 bg-red-50 rounded p-2 mt-3">{error}</div>}

        {/* Inputs */}
        <div className="mt-4">
          <h4 className="text-sm font-semibold mb-2">Inputs</h4>
          {batch.inputs.length === 0 ? (
            <p className="text-sm text-gray-500">
              None logged{batch.outsourced ? ' — built-in per-process defaults apply until the job worker submits actuals.' : ' yet.'}
            </p>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {batch.inputs.map((i) => (
                  <tr key={i.id} className="border-b last:border-0">
                    <td className="py-1.5">{INPUT_LABELS[i.input_type]}</td>
                    <td className="py-1.5 text-right font-mono">{i.quantity.toLocaleString()}</td>
                    <td className="py-1.5 pl-3">
                      <Chip color={i.data_quality === 'measured' ? 'green' : i.data_quality === 'estimated' ? 'amber' : 'gray'}>
                        {QUALITY_LABELS[i.data_quality]}
                      </Chip>
                    </td>
                    <td className="py-1.5 pl-3 text-xs text-gray-500">{i.source}</td>
                    <td className="py-1.5 text-right">
                      <button
                        onClick={async () => {
                          await batchesAPI.deleteInput(batch.id, i.id);
                          await onReload();
                        }}
                        className="text-red-500 text-xs"
                      >
                        remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
            <select
              className="input"
              value={newInput.input_type}
              onChange={(e) => setNewInput({ ...newInput, input_type: e.target.value as BatchInputType })}
            >
              {Object.entries(INPUT_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            <input
              type="number"
              step="0.01"
              min="0"
              className="input"
              placeholder="Quantity"
              value={newInput.quantity || ''}
              onChange={(e) => setNewInput({ ...newInput, quantity: parseFloat(e.target.value) || 0 })}
            />
            <select
              className="input"
              value={newInput.data_quality}
              onChange={(e) => setNewInput({ ...newInput, data_quality: e.target.value as DataQuality })}
            >
              {Object.entries(QUALITY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
            <button
              onClick={addInput}
              disabled={busy || newInput.quantity <= 0}
              className="bg-gray-800 text-white rounded-lg text-sm font-medium disabled:opacity-40"
            >
              Log input
            </button>
          </div>
        </div>
      </div>

      {/* Order allocation with live split bar */}
      {!batch.is_rework && (
        <div className="bg-white rounded-lg shadow p-4 sm:p-6">
          <h4 className="text-sm font-semibold mb-1">Orders served by this batch</h4>
          <p className="text-xs text-gray-500 mb-3">
            Fabric kg defaults to the order's computed demand (units × net weight ÷ (1 − cutting
            waste)). Unclaimed kg become buffer stock with their embodied footprint on completion.
          </p>
          {openOrders.length === 0 ? (
            <p className="text-sm text-gray-500">No open orders — create one on the Orders page.</p>
          ) : (
            <div className="space-y-2">
              {openOrders.map((o) => {
                const checked = attachLines[o.id] !== undefined;
                return (
                  <div key={o.id} className="flex items-center gap-3">
                    <label className="flex items-center gap-2 flex-1 text-sm">
                      <input type="checkbox" checked={checked} onChange={() => toggleOrder(o)} />
                      <span className="font-mono">{o.order_code}</span>
                      <span className="text-gray-500">
                        {o.units} units{o.buyer_name ? ` · ${o.buyer_name}` : ''}
                        {o.fabric_demand_kg ? ` · needs ~${o.fabric_demand_kg} kg` : ''}
                      </span>
                    </label>
                    {checked && (
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        className="input !w-28"
                        value={attachLines[o.id]}
                        onChange={(e) =>
                          setAttachLines((prev) => ({ ...prev, [o.id]: e.target.value }))
                        }
                      />
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {preview.entries.length > 0 && (
            <div className="mt-4">
              <div className="flex h-6 rounded overflow-hidden border border-gray-200">
                {preview.entries.map((e, idx) => (
                  <div
                    key={e.orderId}
                    className={`${SHARE_COLORS[idx % SHARE_COLORS.length]} text-[10px] text-white flex items-center justify-center`}
                    style={{ width: `${Math.min((e.kg / batch.total_fabric_kg) * 100, 100)}%` }}
                    title={`${((e.kg / batch.total_fabric_kg) * 100).toFixed(1)}%`}
                  >
                    {((e.kg / batch.total_fabric_kg) * 100).toFixed(0)}%
                  </div>
                ))}
                {preview.leftover > 0 && (
                  <div
                    className="bg-gray-300 text-[10px] text-gray-700 flex items-center justify-center"
                    style={{ width: `${(preview.leftover / batch.total_fabric_kg) * 100}%` }}
                    title="leftover / buffer"
                  >
                    buffer
                  </div>
                )}
              </div>
              <div className="flex justify-between text-xs text-gray-600 mt-1">
                <span>
                  {preview.claimed.toFixed(1)} / {batch.total_fabric_kg} kg claimed
                </span>
                {preview.over ? (
                  <span className="text-red-600 font-medium">
                    Over-allocated — orders claim more than the batch processed
                  </span>
                ) : (
                  <span>{preview.leftover.toFixed(1)} kg buffer</span>
                )}
              </div>
              <button
                onClick={saveAllocations}
                disabled={busy || preview.over || preview.entries.length === 0}
                className="mt-3 bg-primary text-white px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-40"
              >
                Save split
              </button>
            </div>
          )}
        </div>
      )}
      {batch.is_rework && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
          Rework batch — its consumption is automatically added to the original batch's orders
          pro rata. No separate allocation needed.
        </div>
      )}
    </div>
  );
}

function JobWorkerPanel({
  jobWorkers,
  onCreated,
}: {
  jobWorkers: JobWorker[];
  onCreated: (w: JobWorker) => void;
}) {
  const [name, setName] = useState('');
  const [process, setProcess] = useState<ProcessType>('dyeing');
  const [location, setLocation] = useState('');

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    const created = await jobWorkersAPI.create({
      name: name.trim(),
      process_type: process,
      location: location.trim() || undefined,
    });
    onCreated(created);
    setName('');
    setLocation('');
  };

  return (
    <div className="bg-white rounded-lg shadow p-4 sm:p-6">
      <h3 className="font-semibold mb-1">Job workers</h3>
      <p className="text-xs text-gray-500 mb-3">
        Outside units you outsource processes to (dyeing units, CETPs). Flag a batch as
        outsourced and send them a login-free data request link.
      </p>
      {jobWorkers.length > 0 && (
        <ul className="text-sm mb-3 space-y-1">
          {jobWorkers.map((w) => (
            <li key={w.id} className="flex gap-2">
              <span className="font-medium">{w.name}</span>
              <span className="text-gray-500">
                {PROCESS_LABELS[w.process_type]}
                {w.location ? ` · ${w.location}` : ''}
              </span>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={add} className="grid grid-cols-1 sm:grid-cols-4 gap-2">
        <input className="input" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <select className="input" value={process} onChange={(e) => setProcess(e.target.value as ProcessType)}>
          {Object.entries(PROCESS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <input className="input" placeholder="Location" value={location} onChange={(e) => setLocation(e.target.value)} />
        <button className="bg-gray-800 text-white rounded-lg text-sm font-medium px-4 py-2">Add</button>
      </form>
    </div>
  );
}

function SummaryCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-2xl font-bold ${accent ?? ''}`}>{value}</div>
    </div>
  );
}

function Chip({ children, color }: { children: React.ReactNode; color: 'red' | 'amber' | 'green' | 'gray' | 'teal' }) {
  const colors: Record<string, string> = {
    red: 'bg-red-100 text-red-700',
    amber: 'bg-amber-100 text-amber-700',
    green: 'bg-green-100 text-green-700',
    gray: 'bg-gray-100 text-gray-600',
    teal: 'bg-teal-100 text-teal-700',
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${colors[color]}`}>
      {children}
    </span>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
        {required && <span className="text-red-500"> *</span>}
      </label>
      {children}
    </div>
  );
}
