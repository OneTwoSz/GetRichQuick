import type { OrderFootprint } from '@/types';

// Renders an order's bottom-up footprint: totals, the Allocation Statement
// (per-batch method + share), and the data-quality mix. Used by the
// factory's Orders page AND the public buyer share view — both audiences
// see the same numbers.

const QUALITY_COLORS: Record<string, string> = {
  measured: 'bg-green-500',
  estimated: 'bg-amber-400',
  default_factor: 'bg-gray-400',
};

const QUALITY_LABELS: Record<string, string> = {
  measured: 'Measured',
  estimated: 'Estimated',
  default_factor: 'Default factors',
};

export default function FootprintCard({ footprint }: { footprint: OrderFootprint }) {
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-4 sm:p-6">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Metric label="Total CO₂e" value={`${footprint.co2_kg.toLocaleString()} kg`} />
          <Metric label="Per garment" value={`${footprint.co2_per_garment_kg} kg`} />
          <Metric label="Total water" value={`${footprint.water_l.toLocaleString()} L`} />
          <Metric label="Water / garment" value={`${footprint.water_per_garment_l} L`} />
        </div>
        {(footprint.embodied_co2_kg > 0 || footprint.overhead_co2_kg > 0) && (
          <div className="text-xs text-gray-500 mt-3">
            Includes
            {footprint.embodied_co2_kg > 0 && (
              <> {footprint.embodied_co2_kg} kg CO₂e embodied in consumed buffer fabric</>
            )}
            {footprint.embodied_co2_kg > 0 && footprint.overhead_co2_kg > 0 && ' and'}
            {footprint.overhead_co2_kg > 0 && (
              <> {footprint.overhead_co2_kg} kg CO₂e facility overhead (single-meter reconciliation)</>
            )}
            .
          </div>
        )}
      </div>

      {/* Data-quality mix — the primary-vs-secondary data axis auditors ask about. */}
      <div className="bg-white rounded-lg shadow p-4 sm:p-6">
        <h4 className="text-sm font-semibold mb-2">Data quality (share of footprint)</h4>
        <div className="flex h-5 rounded overflow-hidden border border-gray-200">
          {Object.entries(footprint.quality_mix)
            .filter(([, pct]) => pct > 0)
            .map(([tier, pct]) => (
              <div
                key={tier}
                className={`${QUALITY_COLORS[tier]} text-[10px] text-white flex items-center justify-center`}
                style={{ width: `${pct}%` }}
                title={`${QUALITY_LABELS[tier]}: ${pct}%`}
              >
                {pct >= 12 ? `${pct}%` : ''}
              </div>
            ))}
        </div>
        <div className="flex gap-4 mt-2 text-xs text-gray-600 flex-wrap">
          {Object.entries(footprint.quality_mix).map(([tier, pct]) => (
            <span key={tier} className="flex items-center gap-1">
              <span className={`inline-block w-2.5 h-2.5 rounded-sm ${QUALITY_COLORS[tier]}`} />
              {QUALITY_LABELS[tier]}: {pct}%
            </span>
          ))}
        </div>
      </div>

      {/* Allocation Statement */}
      <div className="bg-white rounded-lg shadow p-4 sm:p-6">
        <h4 className="text-sm font-semibold mb-1">Allocation Statement</h4>
        <p className="text-xs text-gray-500 mb-3">
          Shared batches are split per ISO 14044 — subdivision first, mass allocation by default.
          Shares were fixed at allocation time and are preserved in the audit trail.
        </p>
        {footprint.used_economic_allocation && (
          <div className="text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded p-2 mb-3">
            ⚠ At least one batch used economic (value-based) allocation.
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b">
                <th className="py-2 pr-3">Batch</th>
                <th className="py-2 pr-3">Process</th>
                <th className="py-2 pr-3">Method</th>
                <th className="py-2 pr-3 text-right">Share</th>
                <th className="py-2 pr-3 text-right">kg CO₂e</th>
                <th className="py-2 pr-3 text-right">Water (L)</th>
                <th className="py-2">Flags</th>
              </tr>
            </thead>
            <tbody>
              {footprint.batch_lines.map((line, idx) => (
                <tr key={`${line.batch_id}-${idx}`} className="border-b last:border-0">
                  <td className="py-2 pr-3 font-mono">{line.batch_code}</td>
                  <td className="py-2 pr-3">{line.process_type}</td>
                  <td className="py-2 pr-3">{line.allocation_method}</td>
                  <td className="py-2 pr-3 text-right">{(line.allocated_share * 100).toFixed(1)}%</td>
                  <td className="py-2 pr-3 text-right">{line.co2_kg.toLocaleString()}</td>
                  <td className="py-2 pr-3 text-right">{line.water_l.toLocaleString()}</td>
                  <td className="py-2">
                    <div className="flex gap-1 flex-wrap">
                      {line.is_rework && <Flag color="red">rework</Flag>}
                      {line.outsourced && <Flag color="amber">outsourced</Flag>}
                      {line.data_quality_flags.includes('default_factors') && (
                        <Flag color="gray">default factors</Flag>
                      )}
                      {line.data_quality_flags.includes('economic_allocation') && (
                        <Flag color="amber">economic</Flag>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-xl font-bold text-primary">{value}</div>
    </div>
  );
}

function Flag({ children, color }: { children: React.ReactNode; color: 'red' | 'amber' | 'gray' }) {
  const colors: Record<string, string> = {
    red: 'bg-red-100 text-red-700',
    amber: 'bg-amber-100 text-amber-700',
    gray: 'bg-gray-100 text-gray-600',
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${colors[color]}`}>
      {children}
    </span>
  );
}
