import LinkPanel from '@/components/LinkPanel';
import { useEffect, useState, FormEvent } from 'react';
import { ordersAPI, productsAPI } from '@/services/api';
import type { Order, OrderFormData, OrderFootprint, OrderStatus, Product } from '@/types';
import FootprintCard from '@/components/FootprintCard';

const STATUS_LABELS: Record<OrderStatus, string> = {
  open: 'Open',
  in_production: 'In production',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

const EMPTY_FORM: OrderFormData = {
  order_code: '',
  buyer_name: '',
  product_id: 0,
  units: 0,
  order_value: null,
  status: 'open',
  notes: '',
};

export default function Orders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<OrderFormData>(EMPTY_FORM);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [footprint, setFootprint] = useState<OrderFootprint | null>(null);
  const [footprintLoading, setFootprintLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = orders.find((o) => o.id === selectedId) ?? null;

  useEffect(() => {
    void loadAll();
  }, []);

  useEffect(() => {
    if (selectedId === null) {
      setFootprint(null);
      return;
    }
    setFootprintLoading(true);
    ordersAPI
      .getFootprint(selectedId)
      .then(setFootprint)
      .catch(() => setFootprint(null))
      .finally(() => setFootprintLoading(false));
  }, [selectedId]);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [orderData, productData] = await Promise.all([
        ordersAPI.getAll(),
        productsAPI.getAll(),
      ]);
      setOrders(orderData);
      setProducts(productData);
    } catch (err) {
      console.error('Failed to load orders', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const created = await ordersAPI.create({
        ...formData,
        buyer_name: formData.buyer_name?.trim() || undefined,
        notes: formData.notes?.trim() || undefined,
        order_value: formData.order_value || null,
      });
      setOrders((prev) => [created, ...prev]);
      setShowForm(false);
      setFormData(EMPTY_FORM);
      setSelectedId(created.id);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to create order');
    }
  };

  const [linkBusy, setLinkBusy] = useState(false);
  const shareLink = async (order: Order, rotate = false) => {
    setLinkBusy(true);
    try {
      const updated = await ordersAPI.createShareLink(order.id, rotate);
      setOrders((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
    } finally {
      setLinkBusy(false);
    }
  };
  const revokeShareLink = async (order: Order) => {
    if (!confirm('Revoke this buyer link? Anyone using it will lose access.')) return;
    setLinkBusy(true);
    try {
      const updated = await ordersAPI.revokeShareLink(order.id);
      setOrders((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
    } finally {
      setLinkBusy(false);
    }
  };

  if (loading) return <div className="text-gray-500">Loading orders…</div>;

  return (
    <div className="space-y-6 pb-24 md:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">Orders</h2>
          <p className="text-sm text-gray-600">
            Footprints are reported per order — but computed from the batches that served it.
          </p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="bg-primary text-white px-5 py-3 rounded-lg text-sm font-semibold shadow hover:opacity-90"
        >
          {showForm ? 'Close' : '+ New Order'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4 sm:p-6 space-y-4">
          {error && <div className="text-sm text-red-600 bg-red-50 rounded p-2">{error}</div>}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <Field label="Order code" required>
              <input
                className="input"
                placeholder="PO-2026-104"
                value={formData.order_code}
                onChange={(e) => setFormData({ ...formData, order_code: e.target.value })}
                required
              />
            </Field>
            <Field label="Buyer">
              <input
                className="input"
                value={formData.buyer_name ?? ''}
                onChange={(e) => setFormData({ ...formData, buyer_name: e.target.value })}
              />
            </Field>
            <Field label="Style / SKU" required>
              <select
                className="input"
                value={formData.product_id || ''}
                onChange={(e) => setFormData({ ...formData, product_id: Number(e.target.value) })}
                required
              >
                <option value="">Select style…</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.sku} — {p.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Units" required>
              <input
                type="number"
                min="1"
                className="input"
                value={formData.units || ''}
                onChange={(e) => setFormData({ ...formData, units: parseInt(e.target.value) || 0 })}
                required
              />
            </Field>
            <Field label="Order value (₹, for economic allocation only)">
              <input
                type="number"
                min="0"
                className="input"
                value={formData.order_value ?? ''}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    order_value: e.target.value ? parseFloat(e.target.value) : null,
                  })
                }
              />
            </Field>
            <Field label="Status">
              <select
                className="input"
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value as OrderStatus })}
              >
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </Field>
          </div>
          <button className="bg-primary text-white px-6 py-3 rounded-lg text-sm font-semibold">
            Save order
          </button>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="space-y-2">
          {orders.length === 0 && (
            <div className="text-sm text-gray-500 bg-white rounded-lg shadow p-4">
              No orders yet. Products must exist first — an order is N units of one style.
            </div>
          )}
          {orders.map((o) => (
            <button
              key={o.id}
              onClick={() => setSelectedId(o.id)}
              className={`w-full text-left rounded-lg border p-3 transition ${
                selectedId === o.id
                  ? 'border-primary bg-primary-50'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm font-semibold">{o.order_code}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                  {STATUS_LABELS[o.status]}
                </span>
              </div>
              <div className="text-xs text-gray-600 mt-1">
                {o.units.toLocaleString()} units
                {o.buyer_name ? ` · ${o.buyer_name}` : ''}
                {o.fabric_demand_kg ? ` · needs ~${o.fabric_demand_kg} kg fabric` : ''}
              </div>
            </button>
          ))}
        </div>

        <div className="lg:col-span-2 space-y-4">
          {selected ? (
            <>
              <div className="bg-white rounded-lg shadow p-4 sm:p-6 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-mono font-semibold">{selected.order_code}</h3>
                  <div className="text-sm text-gray-600">
                    {selected.units.toLocaleString()} units
                    {selected.buyer_name ? ` · ${selected.buyer_name}` : ''}
                  </div>
                </div>
                {!selected.share_token && (
                  <button
                    onClick={() => shareLink(selected)}
                    disabled={linkBusy}
                    className="text-sm border border-primary text-primary px-3 py-2 rounded-lg font-medium"
                  >
                    Create buyer share link
                  </button>
                )}
                {selected.share_token && (
                  <div className="w-full">
                    <LinkPanel
                      note="Read-only buyer link: footprint, allocation statement and data-quality mix."
                      url={`${window.location.origin}/share/${selected.share_token}`}
                      expiresAt={selected.share_expires_at}
                      busy={linkBusy}
                      onRotate={() => shareLink(selected, true)}
                      onRevoke={() => revokeShareLink(selected)}
                    />
                  </div>
                )}
              </div>
              {footprintLoading ? (
                <div className="text-sm text-gray-500 bg-white rounded-lg shadow p-6">
                  Computing footprint…
                </div>
              ) : footprint ? (
                <FootprintCard footprint={footprint} />
              ) : (
                <div className="text-sm text-gray-500 bg-white rounded-lg shadow p-6">
                  No batch data yet — attach this order to a production batch to build its
                  footprint bottom-up.
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-gray-500 bg-white rounded-lg shadow p-6">
              Select an order to see its footprint and allocation statement.
            </div>
          )}
        </div>
      </div>
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
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
        {required && <span className="text-red-500"> *</span>}
      </label>
      {children}
    </div>
  );
}
