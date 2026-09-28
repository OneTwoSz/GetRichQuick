import { useEffect, useState, FormEvent } from 'react';
import { productsAPI } from '@/services/api';
import LifecyclePanel from '@/components/LifecyclePanel';
import SupplyChainPanel from '@/components/SupplyChainPanel';
import PassportPanel from '@/components/PassportPanel';
import type {
  Product,
  ProductCarbon,
  ProductFormData,
  BomItemFormData,
  MaterialCategory,
} from '@/types';

const CATEGORY_LABELS: Record<MaterialCategory, string> = {
  fiber: 'Fiber',
  dye: 'Dye',
  chemical: 'Chemical',
  trim: 'Trim',
};

const MATERIAL_KEY_HINTS: Record<MaterialCategory, string[]> = {
  fiber: ['cotton', 'organic_cotton', 'polyester', 'recycled_polyester', 'blend', 'elastane', 'viscose', 'wool', 'linen'],
  dye: ['reactive_dye', 'disperse_dye', 'acid_dye'],
  chemical: ['sodium_carbonate', 'glauber_salt', 'caustic_soda', 'softener'],
  trim: ['button', 'label', 'zipper', 'sewing_thread'],
};

const EMPTY_BOM_ROW: BomItemFormData = {
  material_name: '',
  category: 'fiber',
  material_key: '',
  quantity_per_garment_g: 0,
  notes: '',
};

const EMPTY_FORM: ProductFormData = {
  sku: '',
  name: '',
  description: '',
  fiber_composition: '',
  garment_weight_g: 200,
  cutting_waste_percent: 18,
  recycled_content_pct: 0,
  care_instructions: '',
  target_buyer: '',
  active: true,
  bom: [{ ...EMPTY_BOM_ROW }],
};

export default function Products() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [carbon, setCarbon] = useState<ProductCarbon | null>(null);
  const [carbonLoading, setCarbonLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<ProductFormData>(EMPTY_FORM);

  useEffect(() => {
    void loadProducts();
  }, []);

  useEffect(() => {
    if (selectedId === null) {
      setCarbon(null);
      return;
    }
    setCarbonLoading(true);
    productsAPI
      .getCarbon(selectedId)
      .then(setCarbon)
      .catch((err) => {
        console.error('Failed to load carbon', err);
        setCarbon(null);
      })
      .finally(() => setCarbonLoading(false));
  }, [selectedId]);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const data = await productsAPI.getAll();
      setProducts(data);
      if (data.length && selectedId === null) {
        setSelectedId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load products', err);
    } finally {
      setLoading(false);
    }
  };

  const updateBomRow = (idx: number, patch: Partial<BomItemFormData>) => {
    setFormData((prev) => {
      const next = [...prev.bom];
      next[idx] = { ...next[idx], ...patch };
      return { ...prev, bom: next };
    });
  };

  const addBomRow = () =>
    setFormData((prev) => ({ ...prev, bom: [...prev.bom, { ...EMPTY_BOM_ROW }] }));

  const removeBomRow = (idx: number) =>
    setFormData((prev) => ({ ...prev, bom: prev.bom.filter((_, i) => i !== idx) }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const cleaned: ProductFormData = {
        ...formData,
        bom: formData.bom
          .filter((row) => row.material_name.trim() && row.quantity_per_garment_g > 0)
          .map((row) => ({
            ...row,
            material_key: row.material_key?.trim() || undefined,
            notes: row.notes?.trim() || undefined,
            carbon_factor_override:
              row.carbon_factor_override === undefined ||
              row.carbon_factor_override === null ||
              Number.isNaN(row.carbon_factor_override)
                ? undefined
                : row.carbon_factor_override,
          })),
      };
      const created = await productsAPI.create(cleaned);
      setShowForm(false);
      setFormData(EMPTY_FORM);
      await loadProducts();
      setSelectedId(created.id);
    } catch (err: unknown) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const msg = (err as any)?.response?.data?.detail ?? 'Failed to create product';
      alert(msg);
    }
  };

  const selected = products.find((p) => p.id === selectedId) || null;

  if (loading) {
    return <div className="p-8 text-gray-500">Loading products…</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Products</h1>
          <p className="text-sm text-gray-600 mt-1">
            Per-SKU catalog with bills of materials. The carbon footprint here is
            the per-garment number that feeds your buyer's Digital Product Passport.
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="bg-primary text-white px-4 py-2 rounded-lg hover:bg-primary/90"
        >
          {showForm ? 'Cancel' : '+ Add Product'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="SKU" required>
              <input
                className="input"
                value={formData.sku}
                onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                required
              />
            </Field>
            <Field label="Name" required>
              <input
                className="input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </Field>
            <Field label="Garment weight (g)" required>
              <input
                type="number"
                step="0.1"
                min="0"
                className="input"
                value={formData.garment_weight_g}
                onChange={(e) =>
                  setFormData({ ...formData, garment_weight_g: parseFloat(e.target.value) || 0 })
                }
                required
              />
            </Field>
            <Field label="Cutting waste (%)">
              <input
                type="number"
                step="0.5"
                min="0"
                max="99"
                className="input"
                value={formData.cutting_waste_percent}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    cutting_waste_percent: parseFloat(e.target.value) || 0,
                  })
                }
              />
              <p className="text-xs text-gray-500 mt-1">
                Marker efficiency loss at the cutting table — knitwear typically 15–25%.
              </p>
            </Field>
            <Field label="Recycled content (%)">
              <input
                type="number"
                step="1"
                min="0"
                max="100"
                className="input"
                value={formData.recycled_content_pct}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    recycled_content_pct: parseFloat(e.target.value) || 0,
                  })
                }
              />
            </Field>
            <Field label="Fiber composition">
              <input
                className="input"
                placeholder="e.g. 100% organic cotton"
                value={formData.fiber_composition}
                onChange={(e) => setFormData({ ...formData, fiber_composition: e.target.value })}
              />
            </Field>
            <Field label="Target buyer">
              <input
                className="input"
                placeholder="e.g. H&M Group"
                value={formData.target_buyer}
                onChange={(e) => setFormData({ ...formData, target_buyer: e.target.value })}
              />
            </Field>
          </div>

          <Field label="Description">
            <textarea
              className="input"
              rows={2}
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </Field>

          <div className="border-t pt-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold">Bill of Materials (per garment)</h3>
              <button
                type="button"
                onClick={addBomRow}
                className="text-sm text-primary hover:underline"
              >
                + Add line
              </button>
            </div>
            <div className="space-y-2">
              {formData.bom.map((row, idx) => (
                <div key={idx} className="grid grid-cols-12 gap-2 items-end">
                  <div className="col-span-3">
                    <input
                      className="input"
                      placeholder="Material name"
                      value={row.material_name}
                      onChange={(e) => updateBomRow(idx, { material_name: e.target.value })}
                    />
                  </div>
                  <div className="col-span-2">
                    <select
                      className="input"
                      value={row.category}
                      onChange={(e) =>
                        updateBomRow(idx, { category: e.target.value as MaterialCategory })
                      }
                    >
                      {(['fiber', 'dye', 'chemical', 'trim'] as MaterialCategory[]).map((c) => (
                        <option key={c} value={c}>
                          {CATEGORY_LABELS[c]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-span-3">
                    <input
                      className="input"
                      placeholder="Key (optional)"
                      list={`mkey-${idx}`}
                      value={row.material_key || ''}
                      onChange={(e) => updateBomRow(idx, { material_key: e.target.value })}
                    />
                    <datalist id={`mkey-${idx}`}>
                      {MATERIAL_KEY_HINTS[row.category].map((k) => (
                        <option key={k} value={k} />
                      ))}
                    </datalist>
                  </div>
                  <div className="col-span-2">
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      className="input"
                      placeholder="g/garment"
                      value={row.quantity_per_garment_g || ''}
                      onChange={(e) =>
                        updateBomRow(idx, {
                          quantity_per_garment_g: parseFloat(e.target.value) || 0,
                        })
                      }
                    />
                  </div>
                  <div className="col-span-1">
                    <input
                      type="number"
                      step="0.1"
                      className="input"
                      placeholder="kgCO₂/kg"
                      value={row.carbon_factor_override ?? ''}
                      onChange={(e) =>
                        updateBomRow(idx, {
                          carbon_factor_override: e.target.value
                            ? parseFloat(e.target.value)
                            : null,
                        })
                      }
                    />
                  </div>
                  <div className="col-span-1">
                    <button
                      type="button"
                      onClick={() => removeBomRow(idx)}
                      className="text-red-600 text-sm"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                setFormData(EMPTY_FORM);
              }}
              className="px-4 py-2 border rounded-lg"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="bg-primary text-white px-4 py-2 rounded-lg hover:bg-primary/90"
            >
              Save product
            </button>
          </div>
        </form>
      )}

      {products.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No products yet. Add a SKU to start tracking per-garment data.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-2">
            {products.map((p) => (
              <button
                key={p.id}
                onClick={() => setSelectedId(p.id)}
                className={`w-full text-left p-4 rounded-lg border transition-colors ${
                  selectedId === p.id
                    ? 'border-primary bg-primary-50'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
              >
                <div className="text-xs font-mono text-gray-500">{p.sku}</div>
                <div className="font-semibold">{p.name}</div>
                <div className="text-xs text-gray-600 mt-1">
                  {p.garment_weight_g} g · {p.bom_items.length} BOM lines
                  {p.recycled_content_pct > 0 && (
                    <span className="ml-2 text-green-700">
                      {p.recycled_content_pct}% recycled
                    </span>
                  )}
                </div>
                {p.target_buyer && (
                  <div className="text-xs text-gray-500 mt-1">→ {p.target_buyer}</div>
                )}
              </button>
            ))}
          </div>

          <div className="lg:col-span-2">
            {selected ? (
              <ProductDetail product={selected} carbon={carbon} carbonLoading={carbonLoading} />
            ) : (
              <div className="bg-white rounded-lg shadow p-6 text-gray-500">
                Select a product to view its bill of materials and carbon footprint.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ProductDetail({
  product,
  carbon,
  carbonLoading,
}: {
  product: Product;
  carbon: ProductCarbon | null;
  carbonLoading: boolean;
}) {
  const [tab, setTab] = useState<'lifecycle' | 'supply' | 'passport' | 'bom'>('lifecycle');
  const tabs = [
    { key: 'lifecycle', label: 'Life cycle' },
    { key: 'supply', label: 'Supply chain' },
    { key: 'passport', label: 'Passport' },
    { key: 'bom', label: 'BOM materials' },
  ] as const;
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-xs font-mono text-gray-500">{product.sku}</div>
            <h2 className="text-xl font-bold">{product.name}</h2>
          </div>
          {product.target_buyer && (
            <div className="text-sm text-gray-600">
              Buyer: <span className="font-medium">{product.target_buyer}</span>
            </div>
          )}
        </div>
        {product.fiber_composition && (
          <div className="text-sm text-gray-700 mt-1">{product.fiber_composition}</div>
        )}
        {product.description && (
          <p className="text-sm text-gray-600 mt-2">{product.description}</p>
        )}
        <div className="grid grid-cols-4 gap-4 mt-4 pt-4 border-t">
          <Stat label="Garment weight" value={`${product.garment_weight_g} g`} />
          <Stat label="Cutting waste" value={`${product.cutting_waste_percent ?? 0}%`} />
          <Stat label="Recycled content" value={`${product.recycled_content_pct}%`} />
          <Stat label="BOM lines" value={product.bom_items.length.toString()} />
        </div>
      </div>

      <div className="flex gap-1 border-b border-gray-200 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 -mb-px ${
              tab === t.key
                ? 'border-primary text-primary'
                : 'border-transparent text-gray-600 hover:text-gray-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'lifecycle' && <LifecyclePanel product={product} />}
      {tab === 'supply' && <SupplyChainPanel product={product} />}
      {tab === 'passport' && <PassportPanel product={product} />}

      {tab === 'bom' && (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="font-semibold mb-3">Per-garment carbon footprint</h3>
        {carbonLoading ? (
          <div className="text-sm text-gray-500">Calculating…</div>
        ) : carbon ? (
          <>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="p-4 bg-primary-50 rounded">
                <div className="text-xs text-gray-600">Theoretical (from BOM)</div>
                <div className="text-2xl font-bold text-primary">
                  {carbon.total_per_garment_kg.toFixed(3)}{' '}
                  <span className="text-sm font-normal">kg CO₂e</span>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Materials only — see Life cycle for the full footprint
                </div>
              </div>
              <div className="p-4 bg-gray-50 rounded">
                <div className="text-xs text-gray-600">
                  Actual observed{' '}
                  {carbon.batches_observed > 0 && `(${carbon.batches_observed} batches)`}
                </div>
                <div className="text-2xl font-bold text-gray-700">
                  {carbon.actual_per_garment_kg !== null
                    ? `${carbon.actual_per_garment_kg.toFixed(3)}`
                    : '—'}{' '}
                  <span className="text-sm font-normal">kg CO₂e</span>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Includes electricity, water treatment, transport
                </div>
              </div>
            </div>

            <table className="w-full text-sm">
              <thead className="border-b">
                <tr className="text-left text-xs text-gray-600">
                  <th className="py-2">Material</th>
                  <th className="py-2">Category</th>
                  <th className="py-2 text-right">g/garment</th>
                  <th className="py-2 text-right">kgCO₂/kg</th>
                  <th className="py-2 text-right">kgCO₂/garment</th>
                </tr>
              </thead>
              <tbody>
                {carbon.breakdown.map((b, i) => (
                  <tr key={i} className="border-b last:border-b-0">
                    <td className="py-2">{b.material_name}</td>
                    <td className="py-2 text-gray-600">{CATEGORY_LABELS[b.category]}</td>
                    <td className="py-2 text-right tabular-nums">
                      {b.quantity_per_garment_g.toFixed(1)}
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      {b.carbon_factor.toFixed(2)}
                    </td>
                    <td className="py-2 text-right tabular-nums font-medium">
                      {b.emissions_per_garment_kg.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="font-semibold bg-gray-50">
                  <td className="py-2" colSpan={4}>
                    Total
                  </td>
                  <td className="py-2 text-right tabular-nums">
                    {carbon.total_per_garment_kg.toFixed(4)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </>
        ) : (
          <div className="text-sm text-gray-500">No carbon data available.</div>
        )}
      </div>
      )}

      {product.care_instructions && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold mb-2">Care instructions</h3>
          <p className="text-sm text-gray-700">{product.care_instructions}</p>
        </div>
      )}
    </div>
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
    <label className="block">
      <span className="text-sm font-medium text-gray-700">
        {label} {required && <span className="text-red-500">*</span>}
      </span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}
