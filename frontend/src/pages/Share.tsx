import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { publicAPI } from '@/services/api';
import type { OrderFootprint } from '@/types';
import FootprintCard from '@/components/FootprintCard';

// Public buyer view — no login. A factory sends this link to answer any
// brand portal request in one click: footprint + allocation statement +
// data-quality mix, straight from batch-level primary data.
export default function Share() {
  const { token } = useParams<{ token: string }>();
  const [footprint, setFootprint] = useState<OrderFootprint | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    publicAPI
      .getSharedFootprint(token)
      .then(setFootprint)
      .catch(() => setError('This share link is invalid or has been removed.'))
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-primary">GreenThread</h1>
          <span className="text-xs text-gray-500">Verified production data · read-only</span>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-4 py-6">
        {loading && <div className="text-gray-500">Loading…</div>}
        {error && (
          <div className="bg-white rounded-lg shadow p-6 text-sm text-red-600">{error}</div>
        )}
        {footprint && (
          <div className="space-y-4">
            <div className="bg-white rounded-lg shadow p-4 sm:p-6">
              <div className="text-xs text-gray-500 uppercase tracking-wide">Order footprint</div>
              <h2 className="text-lg font-bold font-mono">{footprint.order_code}</h2>
              <div className="text-sm text-gray-600">
                {footprint.product_name && (
                  <>
                    {footprint.product_name}
                    {footprint.product_sku ? ` (${footprint.product_sku})` : ''} ·{' '}
                  </>
                )}
                {footprint.units.toLocaleString()} units
                {footprint.buyer_name ? ` · for ${footprint.buyer_name}` : ''}
              </div>
            </div>
            <FootprintCard footprint={footprint} />
            <p className="text-xs text-gray-500 text-center pb-6">
              Bottom-up footprint computed from batch-level primary production data recorded in
              GreenThread. Allocation follows ISO 14044; shares and inputs are audit-trailed.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
