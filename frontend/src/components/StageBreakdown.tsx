import type { StageDataSource } from '@/types';
import {
  COUNTRIES,
  QUALITY_COLORS,
  QUALITY_LABELS,
  SOURCE_COLORS,
  SOURCE_LABELS,
} from '@/components/lifecycleLabels';

// Per-stage footprint bars, coloured by where each stage's data came from.
// Shared by the product page and the public passport.

export interface StageRow {
  stage: string;
  label: string;
  co2e_kg: number;
  water_l: number;
  data_source: StageDataSource;
  country?: string | null;
  sources?: string[];
  flags?: string[];
}

export function StageBreakdown({ stages }: { stages: StageRow[] }) {
  const max = Math.max(...stages.map((s) => s.co2e_kg), 0.0001);
  const total = stages.reduce((sum, s) => sum + s.co2e_kg, 0);
  return (
    <div className="space-y-3">
      {stages.map((s) => {
        const colors = SOURCE_COLORS[s.data_source] ?? SOURCE_COLORS.none;
        const pct = total > 0 ? (s.co2e_kg / total) * 100 : 0;
        return (
          <div key={s.stage}>
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="font-medium">{s.label}</span>
              <span className="tabular-nums text-gray-700 whitespace-nowrap">
                {s.co2e_kg.toFixed(3)} kg
                <span className="text-xs text-gray-500 ml-1">({pct.toFixed(0)}%)</span>
              </span>
            </div>
            <div className="h-2.5 bg-gray-100 rounded mt-1 overflow-hidden">
              <div
                className={`h-full ${colors.bar} rounded`}
                style={{ width: `${(s.co2e_kg / max) * 100}%` }}
              />
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-gray-500">
              <span className={`px-1.5 py-0.5 rounded ${colors.badge}`}>
                {SOURCE_LABELS[s.data_source] ?? s.data_source}
              </span>
              {s.country && <span>{COUNTRIES[s.country] ?? s.country}</span>}
              {s.water_l >= 0.05 && <span>{s.water_l.toFixed(1)} L water</span>}
              {s.flags?.map((f) => (
                <span key={f} className="text-amber-700">⚠ {f.replace(/_/g, ' ')}</span>
              ))}
            </div>
            {s.sources && s.sources.length > 0 && (
              <div className="text-[11px] text-gray-400 mt-0.5 truncate" title={s.sources.join('\n')}>
                {s.sources.join(' · ')}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function QualityMixBar({ mix }: { mix: Record<string, number> }) {
  const tiers = ['measured', 'estimated', 'default_factor'];
  return (
    <div>
      <div className="flex h-3 rounded overflow-hidden bg-gray-100">
        {tiers.map((tier) =>
          (mix[tier] ?? 0) > 0 ? (
            <div
              key={tier}
              className={QUALITY_COLORS[tier]}
              style={{ width: `${mix[tier]}%` }}
              title={`${QUALITY_LABELS[tier]}: ${mix[tier]}%`}
            />
          ) : null
        )}
      </div>
      <div className="flex flex-wrap gap-3 mt-1.5 text-xs text-gray-600">
        {tiers.map((tier) => (
          <span key={tier} className="flex items-center gap-1">
            <span className={`inline-block w-2.5 h-2.5 rounded-sm ${QUALITY_COLORS[tier]}`} />
            {QUALITY_LABELS[tier]}: {(mix[tier] ?? 0).toFixed(0)}%
          </span>
        ))}
      </div>
    </div>
  );
}
