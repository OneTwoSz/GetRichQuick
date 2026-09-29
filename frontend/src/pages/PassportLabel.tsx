import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Printer } from 'lucide-react';
import { publicAPI } from '@/services/api';
import type { PublicPassport } from '@/types';

// Print sheet of passport QR codes sized for wash-care labels and hangtags.
// Sizes are real millimetres (CSS mm units); print at 100% scale. The QR
// uses high error correction (Q, ~25% recoverable) and the full 4-module
// quiet zone so it still scans on printed satin/fabric labels after washing.

const SIZES = [15, 20, 25, 30]; // QR edge length in mm
const MIN_RECOMMENDED_MM = 18;

export default function PassportLabel() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<PublicPassport | null>(null);
  const [error, setError] = useState(false);
  const [size, setSize] = useState(20);
  const [copies, setCopies] = useState(12);
  const [showSku, setShowSku] = useState(true);

  useEffect(() => {
    if (token) publicAPI.getPassport(token).then(setData).catch(() => setError(true));
  }, [token]);

  if (error || !token) {
    return <div className="p-8 text-sm text-red-600">This passport could not be found.</div>;
  }

  const qr = publicAPI.passportQrUrl(token, 'q');
  const sku = data?.payload.product.sku;

  return (
    <div className="min-h-screen bg-gray-50 print:bg-[#ffffff]">
      <div className="mx-auto max-w-4xl space-y-4 p-6 print:hidden">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-gray-900">Care-label QR sheet</h1>
            <p className="mt-1 text-sm text-gray-500">
              {data ? `${data.payload.product.name} · ${sku}` : 'Loading…'} — print at 100% scale (no “fit to page”).
            </p>
          </div>
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-600"
          >
            <Printer className="h-4 w-4" aria-hidden /> Print
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-6 rounded-xl bg-white p-4 text-sm shadow">
          <label className="flex items-center gap-2">
            <span className="text-gray-600">QR size</span>
            <select className="input !w-auto" value={size} onChange={(e) => setSize(Number(e.target.value))}>
              {SIZES.map((s) => (
                <option key={s} value={s}>{s} mm</option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <span className="text-gray-600">Copies</span>
            <input
              type="number"
              min={1}
              max={200}
              className="input !w-20"
              value={copies}
              onChange={(e) => setCopies(Math.min(200, Math.max(1, Number(e.target.value) || 1)))}
            />
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={showSku} onChange={(e) => setShowSku(e.target.checked)} />
            <span className="text-gray-600">Print SKU under the code</span>
          </label>
        </div>

        {size < MIN_RECOMMENDED_MM && (
          <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Below {MIN_RECOMMENDED_MM} mm, older phones and woven labels may not scan reliably. Test-print one
            and scan it before a production run.
          </p>
        )}
      </div>

      {/* The sheet itself always prints black on white, whatever the theme. */}
      <div className="mx-auto max-w-4xl px-6 pb-10 print:max-w-none print:p-0">
        <div className="flex flex-wrap gap-[6mm] rounded-xl bg-[#ffffff] p-[8mm] shadow print:rounded-none print:shadow-none">
          {Array.from({ length: copies }, (_, i) => (
            <div
              key={i}
              className="flex flex-col items-center border border-dashed border-[#d4d4d4] p-[2mm] text-[#111111] print:break-inside-avoid"
              style={{ width: `${size + 4}mm` }}
            >
              <img src={qr} alt="" style={{ width: `${size}mm`, height: `${size}mm` }} />
              <div className="mt-[1mm] text-center font-semibold leading-tight" style={{ fontSize: '5.5pt' }}>
                Scan for product passport
              </div>
              {showSku && sku && (
                <div className="text-center font-mono leading-tight" style={{ fontSize: '5pt' }}>{sku}</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
