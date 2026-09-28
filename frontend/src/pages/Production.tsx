import { Spinner } from '@/components/ui';
import { useState, useEffect, FormEvent } from 'react';
import { productionAPI, carbonAPI } from '@/services/api';
import type { ProductionRecord, ProductionFormData, FabricType, CarbonSummary } from '@/types';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import BillUpload from '@/components/BillUpload';
import { enqueueWrite } from '@/services/offlineQueue';

// Map extracted OCR fields into ProductionFormData fields.
// The parent owns the merge because different hints touch different subsets
// of the form, and a bill doesn't supply a date we should blindly overwrite.
function mergeElectricityBill(
  prev: ProductionFormData,
  fields: Record<string, unknown>,
): ProductionFormData {
  const kwh = Number(fields.units_consumed_kwh);
  if (Number.isFinite(kwh) && kwh > 0) {
    return { ...prev, electricity_kwh: kwh };
  }
  return prev;
}

function mergeWaterBill(
  prev: ProductionFormData,
  fields: Record<string, unknown>,
): ProductionFormData {
  const kl = Number(fields.water_consumed_kl);
  if (Number.isFinite(kl) && kl > 0) {
    return { ...prev, water_liters: kl * 1000 };
  }
  return prev;
}

function mergeFabricInvoice(
  prev: ProductionFormData,
  fields: Record<string, unknown>,
): ProductionFormData {
  const items = Array.isArray(fields.items) ? (fields.items as any[]) : [];
  if (items.length === 0) return prev;
  const totalKg = items.reduce((sum, it) => sum + (Number(it.quantity_kg) || 0), 0);
  const firstType = String(items[0]?.fabric_type ?? '').toLowerCase();
  const allowed: FabricType[] = ['cotton', 'organic_cotton', 'polyester', 'blend'];
  const nextType = (allowed as string[]).includes(firstType) ? (firstType as FabricType) : prev.fabric_type;
  return { ...prev, fabric_type: nextType, fabric_quantity_kg: totalKg || prev.fabric_quantity_kg };
}

export default function Production() {
  const [records, setRecords] = useState<ProductionRecord[]>([]);
  const [carbonSummary, setCarbonSummary] = useState<CarbonSummary | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState<ProductionFormData>({
    date: new Date().toISOString().split('T')[0],
    fabric_type: 'cotton',
    fabric_quantity_kg: 0,
    dye_quantity_kg: 0,
    chemicals_kg: 0,
    electricity_kwh: 0,
    water_liters: 0,
    wastewater_treated_liters: 0,
    garments_produced: 0,
    transport_distance_km: 0,
    transport_mode: undefined,
    notes: '',
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const now = new Date();
      const recordsData = await productionAPI.getAll({
        month: now.getMonth() + 1,
        year: now.getFullYear(),
      });
      setRecords(recordsData);

      // Get carbon summary for this month
      const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
      const carbonData = await carbonAPI.getSummary(
        startOfMonth.toISOString(),
        now.toISOString()
      );
      setCarbonSummary(carbonData);
    } catch (err) {
      console.error('Failed to load production data', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const emptyForm: ProductionFormData = {
      date: new Date().toISOString().split('T')[0],
      fabric_type: 'cotton',
      fabric_quantity_kg: 0,
      dye_quantity_kg: 0,
      chemicals_kg: 0,
      electricity_kwh: 0,
      water_liters: 0,
      wastewater_treated_liters: 0,
      garments_produced: 0,
      transport_distance_km: 0,
      transport_mode: undefined,
      notes: '',
    };

    const offline = typeof navigator !== 'undefined' && navigator.onLine === false;
    try {
      if (offline) {
        await enqueueWrite('POST', '/production', formData);
        setShowForm(false);
        setFormData(emptyForm);
        return;
      }
      await productionAPI.create(formData);
      setShowForm(false);
      setFormData(emptyForm);
      loadData();
    } catch (err: any) {
      // If the request failed because we're actually offline (no response),
      // fall back to queueing rather than losing the entry.
      if (!err?.response) {
        try {
          await enqueueWrite('POST', '/production', formData);
          setShowForm(false);
          setFormData(emptyForm);
          return;
        } catch (queueErr) {
          console.error('Failed to queue offline write', queueErr);
        }
      }
      console.error('Failed to create production record', err);
      alert('Failed to save production data');
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: ['fabric_type', 'transport_mode', 'notes', 'date'].includes(name)
        ? value || (name === 'transport_mode' ? undefined : '')
        : parseFloat(value) || 0,
    }));
  };

  if (loading) {
    return <Spinner />;
  }

  // Theme-aware series colours (defined per theme in index.css).
  const COLORS = [1, 2, 3, 4, 5].map((n) => `rgb(var(--chart-${n}))`);

  const chartData = carbonSummary
    ? [
        { name: 'Materials', value: carbonSummary.breakdown.materials },
        { name: 'Energy', value: carbonSummary.breakdown.energy },
        { name: 'Water Treatment', value: carbonSummary.breakdown.water_treatment },
        { name: 'Chemicals', value: carbonSummary.breakdown.chemicals },
        { name: 'Transport', value: carbonSummary.breakdown.transport },
      ].filter((item) => item.value > 0)
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-gray-900 sm:text-[28px]">Production Data</h1>
          <p className="mt-1 text-sm text-gray-600">Log and track your production batches</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-600"
        >
          {showForm ? 'Cancel' : '+ Log Production'}
        </button>
      </div>

      {/* Carbon Summary Card */}
      {carbonSummary && carbonSummary.total_carbon_kg > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Carbon Footprint This Month</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <div className="space-y-4">
                <div>
                  <div className="text-sm text-gray-600">Total Carbon Footprint</div>
                  <div className="text-3xl font-bold text-primary">
                    {carbonSummary.total_carbon_kg.toFixed(2)} kg CO₂e
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Per Garment</div>
                  <div className="text-2xl font-bold text-primary">
                    {carbonSummary.carbon_per_garment_kg.toFixed(3)} kg CO₂e
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Total Garments</div>
                  <div className="text-2xl font-bold text-gray-900">
                    {carbonSummary.total_garments.toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
            <div>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    innerRadius={52}
                    outerRadius={80}
                    paddingAngle={2}
                    stroke="rgb(var(--white))"
                    strokeWidth={2}
                    dataKey="value"
                  >
                    {chartData.map((_entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: 'rgb(var(--white))',
                      border: '1px solid rgb(var(--hairline))',
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    itemStyle={{ color: 'rgb(var(--gray-900))' }}
                    formatter={(v: number) => `${v.toFixed(1)} kg CO₂e`}
                  />
                  <Legend
                    iconType="circle"
                    iconSize={8}
                    formatter={(value) => <span style={{ color: 'rgb(var(--gray-600))', fontSize: 12 }}>{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Production Form */}
      {showForm && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">Log Production Batch</h2>
          </div>
          <form onSubmit={handleSubmit} className="p-6 space-y-6">
            <div className="space-y-3">
              <div className="text-sm font-medium text-gray-900">
                Skip typing — upload a bill or invoice
              </div>
              <p className="text-xs text-gray-600">
                Upload a phone photo or PDF; we'll pre-fill the matching fields. Always review the
                values before saving.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <BillUpload
                  hint="electricity_bill"
                  helpText="TANGEDCO / TNEB bill — fills electricity (kWh)."
                  onApply={(fields) => setFormData((prev) => mergeElectricityBill(prev, fields))}
                />
                <BillUpload
                  hint="water_bill"
                  helpText="Metered water bill — fills water (litres)."
                  onApply={(fields) => setFormData((prev) => mergeWaterBill(prev, fields))}
                />
                <BillUpload
                  hint="fabric_invoice"
                  helpText="Supplier invoice — fills fabric type & quantity."
                  onApply={(fields) => setFormData((prev) => mergeFabricInvoice(prev, fields))}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700">Date</label>
                <input
                  type="date"
                  name="date"
                  value={formData.date}
                  onChange={handleChange}
                  required
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Fabric Type</label>
                <select
                  name="fabric_type"
                  value={formData.fabric_type}
                  onChange={handleChange}
                  required
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="cotton">Cotton</option>
                  <option value="organic_cotton">Organic Cotton</option>
                  <option value="polyester">Polyester</option>
                  <option value="blend">Cotton-Poly Blend</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Fabric Quantity (kg)</label>
                <input
                  type="number"
                  name="fabric_quantity_kg"
                  value={formData.fabric_quantity_kg}
                  onChange={handleChange}
                  required
                  min="0"
                  step="0.01"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Garments Produced</label>
                <input
                  type="number"
                  name="garments_produced"
                  value={formData.garments_produced}
                  onChange={handleChange}
                  required
                  min="1"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Dye Quantity (kg)</label>
                <input
                  type="number"
                  name="dye_quantity_kg"
                  value={formData.dye_quantity_kg}
                  onChange={handleChange}
                  min="0"
                  step="0.01"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Chemicals (kg)</label>
                <input
                  type="number"
                  name="chemicals_kg"
                  value={formData.chemicals_kg}
                  onChange={handleChange}
                  min="0"
                  step="0.01"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Electricity (kWh)</label>
                <input
                  type="number"
                  name="electricity_kwh"
                  value={formData.electricity_kwh}
                  onChange={handleChange}
                  min="0"
                  step="0.01"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Water (liters)</label>
                <input
                  type="number"
                  name="water_liters"
                  value={formData.water_liters}
                  onChange={handleChange}
                  min="0"
                  step="0.01"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Wastewater Treated (liters)
                </label>
                <input
                  type="number"
                  name="wastewater_treated_liters"
                  value={formData.wastewater_treated_liters}
                  onChange={handleChange}
                  min="0"
                  step="0.01"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Transport Distance (km)</label>
                <input
                  type="number"
                  name="transport_distance_km"
                  value={formData.transport_distance_km}
                  onChange={handleChange}
                  min="0"
                  step="0.01"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Transport Mode</label>
                <select
                  name="transport_mode"
                  value={formData.transport_mode || ''}
                  onChange={handleChange}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="">None</option>
                  <option value="truck">Truck</option>
                  <option value="sea_freight">Sea Freight</option>
                </select>
              </div>

              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700">Notes</label>
                <textarea
                  name="notes"
                  value={formData.notes}
                  onChange={handleChange}
                  rows={3}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="Any additional notes about this batch..."
                />
              </div>
            </div>

            <button
              type="submit"
              className="w-full py-2 px-4 bg-primary text-white rounded-lg hover:bg-primary-600"
            >
              Save Production Data
            </button>
          </form>
        </div>
      )}

      {/* Records List */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Recent Production Records</h2>
        </div>
        <div className="overflow-x-auto">
          {records.length === 0 ? (
            <div className="p-6 text-center text-gray-500">
              No production records for this month. Click "Log Production" to add your first batch.
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Date
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Fabric Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Fabric (kg)
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Garments
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Water (L)
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Energy (kWh)
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {records.map((record) => (
                  <tr key={record.id}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {new Date(record.date).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {record.fabric_type.replace('_', ' ')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {record.fabric_quantity_kg.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {record.garments_produced}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {record.water_liters.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {record.electricity_kwh.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
