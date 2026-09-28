import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { lifecycleAPI, suppliersAPI } from '@/services/api';
import type { Product, ProductSupplierLink, Supplier, SupplyChainStage } from '@/types';
import { COUNTRIES, SUPPLY_STAGES, SUPPLY_STAGE_LABELS } from '@/components/lifecycleLabels';

// Per-product traceability map: who performs each upstream stage, where,
// with what certifications — plus a one-click login-free data request.
export default function SupplyChainPanel({ product }: { product: Product }) {
  const [links, setLinks] = useState<ProductSupplierLink[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [requestUrl, setRequestUrl] = useState<{ stage: SupplyChainStage; url: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [l, s] = await Promise.all([lifecycleAPI.getSuppliers(product.id), suppliersAPI.getAll()]);
    setLinks(l);
    setSuppliers(s);
  }, [product.id]);

  useEffect(() => {
    setRequestUrl(null);
    load().catch(() => setError('Could not load the supply chain.'));
  }, [load]);

  const byStage = Object.fromEntries(links.map((l) => [l.stage, l.supplier])) as Partial<
    Record<SupplyChainStage, Supplier>
  >;

  const change = async (stage: SupplyChainStage, value: string) => {
    setError(null);
    try {
      if (value === '') await lifecycleAPI.unlinkSupplier(product.id, stage);
      else await lifecycleAPI.linkSupplier(product.id, stage, parseInt(value));
      await load();
    } catch {
      setError('Could not update the link.');
    }
  };

  const requestData = async (stage: SupplyChainStage, supplier: Supplier) => {
    const req = await suppliersAPI.createDataRequest(supplier.id, { stage });
    setRequestUrl({ stage, url: `${window.location.origin}/supplier-data/${req.token}` });
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-baseline justify-between mb-1">
        <h3 className="font-semibold">Supply chain</h3>
        <Link to="/suppliers" className="text-sm text-primary">Manage suppliers →</Link>
      </div>
      <p className="text-xs text-gray-500 mb-4">
        Link the facility behind each stage. Their location sets the grid factor; their submitted
        data replaces defaults with supplier primary data.
      </p>
      {error && <div className="text-sm text-red-600 mb-2">{error}</div>}
      <div className="divide-y">
        {SUPPLY_STAGES.map((stage) => {
          const current = byStage[stage];
          const options = suppliers.filter((s) => s.stage === stage || s.id === current?.id);
          return (
            <div key={stage} className="py-3 grid grid-cols-1 sm:grid-cols-3 gap-2 items-center">
              <div className="text-sm font-medium">{SUPPLY_STAGE_LABELS[stage]}</div>
              <select
                className="input"
                value={current?.id ?? ''}
                onChange={(e) => change(stage, e.target.value)}
              >
                <option value="">
                  {stage === 'assembly' ? 'This factory (in-house)' : 'Not linked — defaults'}
                </option>
                {options.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} · {s.city ? `${s.city}, ` : ''}{s.country}
                  </option>
                ))}
              </select>
              <div className="text-xs text-gray-600 flex flex-wrap items-center gap-2">
                {current ? (
                  <>
                    <span>Tier {current.tier}</span>
                    <span>{COUNTRIES[current.country] ?? current.country}</span>
                    {current.certifications.map((c) => (
                      <span key={c.name} className="px-1.5 py-0.5 rounded bg-green-50 text-green-700">
                        {c.name}
                      </span>
                    ))}
                    {stage !== 'raw_materials' && stage !== 'trims_packaging' && (
                      <button
                        className="text-primary font-medium"
                        onClick={() => requestData(stage, current)}
                      >
                        Request data
                      </button>
                    )}
                  </>
                ) : (
                  options.length === 0 && stage !== 'assembly' && (
                    <span className="text-gray-400">No suppliers for this stage yet</span>
                  )
                )}
              </div>
            </div>
          );
        })}
      </div>
      {requestUrl && (
        <div className="mt-4 p-3 bg-primary-50 rounded text-sm">
          <div className="font-medium mb-1">
            Send this link to the supplier (WhatsApp / email) — no login needed:
          </div>
          <div className="flex gap-2">
            <input readOnly className="input font-mono text-xs" value={requestUrl.url} />
            <button
              className="bg-primary text-white px-3 rounded-lg text-sm"
              onClick={() => navigator.clipboard?.writeText(requestUrl.url)}
            >
              Copy
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
