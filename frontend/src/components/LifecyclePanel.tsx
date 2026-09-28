import { useCallback, useEffect, useState } from 'react';
import { lifecycleAPI } from '@/services/api';
import type {
  Boundary,
  EndOfLife,
  LifecycleFootprint,
  LifecycleSettings,
  Product,
  ScenarioResult,
  TransportModeLC,
  ValidationResult,
} from '@/types';
import { QualityMixBar, StageBreakdown } from '@/components/StageBreakdown';
import {
  BOUNDARY_LABELS,
  COUNTRIES,
  FIBRE_KEYS,
  PACKAGING_KEYS,
  humanize,
} from '@/components/lifecycleLabels';

// Product life-cycle footprint: per-stage breakdown with data sources,
// primary-data share, the automated checks, life-cycle settings and an
// ecodesign scenario comparison.
export default function LifecyclePanel({
  product,
  onValidation,
}: {
  product: Product;
  onValidation?: (v: ValidationResult) => void;
}) {
  const [footprint, setFootprint] = useState<LifecycleFootprint | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [settings, setSettings] = useState<LifecycleSettings | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [fp, v, s] = await Promise.all([
        lifecycleAPI.getFootprint(product.id),
        lifecycleAPI.validate(product.id),
        lifecycleAPI.getSettings(product.id),
      ]);
      setFootprint(fp);
      setValidation(v);
      setSettings(s);
      onValidation?.(v);
    } catch {
      setError('Could not load the life-cycle footprint.');
    }
  }, [product.id, onValidation]);

  useEffect(() => {
    setFootprint(null);
    load();
  }, [load]);

  if (error) return <div className="bg-white rounded-lg shadow p-6 text-sm text-red-600">{error}</div>;
  if (!footprint || !settings) {
    return <div className="bg-white rounded-lg shadow p-6 text-sm text-gray-500">Calculating…</div>;
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex flex-wrap items-start justify-between gap-2 mb-4">
          <div>
            <h3 className="font-semibold">Life-cycle footprint per garment</h3>
            <p className="text-xs text-gray-500">
              {BOUNDARY_LABELS[footprint.boundary]} · ISO 14040/44-aligned
              {footprint.excluded_stages.length > 0 &&
                ` · excludes ${footprint.excluded_stages.map(humanize).join(', ')}`}
            </p>
          </div>
          <button
            onClick={() => setShowSettings((s) => !s)}
            className="text-sm text-primary font-medium"
          >
            {showSettings ? 'Hide settings' : 'Life-cycle settings'}
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
          <Metric label="Carbon" value={footprint.co2e_kg.toFixed(2)} unit="kg CO₂e" strong />
          <Metric label="Water" value={footprint.water_l.toFixed(0)} unit="L" />
          <Metric label="Energy" value={footprint.energy_kwh.toFixed(2)} unit="kWh" />
          <Metric
            label="Primary data"
            value={footprint.primary_share_pct.toFixed(0)}
            unit="% of CO₂e"
            strong
          />
        </div>

        <div className="mb-5">
          <div className="text-xs font-medium text-gray-600 mb-1">Data quality mix</div>
          <QualityMixBar mix={footprint.quality_mix} />
        </div>

        <StageBreakdown stages={footprint.stages} />

        {showSettings && (
          <SettingsEditor
            productId={product.id}
            initial={settings}
            onSaved={() => {
              setShowSettings(false);
              load();
            }}
          />
        )}
      </div>

      {validation && <ValidationCard validation={validation} />}

      <ScenarioCard product={product} />
    </div>
  );
}

function Metric({
  label,
  value,
  unit,
  strong,
}: {
  label: string;
  value: string;
  unit: string;
  strong?: boolean;
}) {
  return (
    <div className={`p-3 rounded ${strong ? 'bg-primary-50' : 'bg-gray-50'}`}>
      <div className="text-xs text-gray-600">{label}</div>
      <div className={`text-xl font-bold ${strong ? 'text-primary' : 'text-gray-800'}`}>
        {value} <span className="text-xs font-normal text-gray-600">{unit}</span>
      </div>
    </div>
  );
}

const SEVERITY_STYLE = {
  error: 'bg-red-50 text-red-800 border-red-200',
  warning: 'bg-amber-50 text-amber-800 border-amber-200',
  info: 'bg-gray-50 text-gray-700 border-gray-200',
};

function ValidationCard({ validation }: { validation: ValidationResult }) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">Automated checks</h3>
        <span
          className={`text-xs px-2 py-1 rounded ${
            validation.publishable ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
          }`}
        >
          {validation.publishable ? 'Ready to publish' : `${validation.errors} blocking error(s)`}
        </span>
      </div>
      {validation.issues.length === 0 ? (
        <p className="text-sm text-gray-600">
          ✓ Units, ranges, duplicates and bill reconciliation all look consistent.
        </p>
      ) : (
        <ul className="space-y-2">
          {validation.issues.map((issue, i) => (
            <li key={i} className={`text-sm border rounded p-2 ${SEVERITY_STYLE[issue.severity]}`}>
              <span className="font-semibold uppercase text-[10px] mr-2">{issue.severity}</span>
              {issue.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SettingsEditor({
  productId,
  initial,
  onSaved,
}: {
  productId: number;
  initial: LifecycleSettings;
  onSaved: () => void;
}) {
  const [s, setS] = useState<LifecycleSettings>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await lifecycleAPI.saveSettings(productId, {
        ...s,
        packaging: s.packaging.filter((p) => p.grams > 0),
        distribution: s.distribution.filter((d) => d.distance_km > 0),
      });
      onSaved();
    } catch {
      setError('Could not save settings — check the values.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-6 pt-4 border-t space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="font-medium text-gray-700">System boundary</span>
          <select
            className="input mt-1"
            value={s.boundary}
            onChange={(e) => setS({ ...s, boundary: e.target.value as Boundary })}
          >
            {Object.entries(BOUNDARY_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="font-medium text-gray-700">End of life</span>
          <select
            className="input mt-1"
            value={s.end_of_life}
            onChange={(e) => setS({ ...s, end_of_life: e.target.value as EndOfLife })}
          >
            {['eu_average', 'landfill', 'incineration', 'recycling'].map((k) => (
              <option key={k} value={k}>{humanize(k)}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="font-medium text-gray-700">Washes over lifetime</span>
          <input
            type="number"
            min={0}
            className="input mt-1"
            value={s.washes}
            onChange={(e) => setS({ ...s, washes: parseInt(e.target.value) || 0 })}
          />
        </label>
        <label className="block text-sm">
          <span className="font-medium text-gray-700">Use country</span>
          <select
            className="input mt-1"
            value={s.use_country}
            onChange={(e) => setS({ ...s, use_country: e.target.value })}
          >
            {Object.entries(COUNTRIES).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={s.tumble_dry}
          onChange={(e) => setS({ ...s, tumble_dry: e.target.checked })}
        />
        Consumer tumble-dries
      </label>

      <div>
        <div className="text-sm font-medium text-gray-700 mb-1">Packaging per garment</div>
        {s.packaging.map((p, i) => (
          <div key={i} className="flex gap-2 mb-2">
            <select
              className="input flex-1"
              value={p.material_key}
              onChange={(e) => {
                const next = [...s.packaging];
                next[i] = { ...p, material_key: e.target.value };
                setS({ ...s, packaging: next });
              }}
            >
              {PACKAGING_KEYS.map((k) => (
                <option key={k} value={k}>{humanize(k)}</option>
              ))}
            </select>
            <input
              type="number"
              min={0}
              step="0.1"
              className="input !w-24"
              placeholder="g"
              value={p.grams || ''}
              onChange={(e) => {
                const next = [...s.packaging];
                next[i] = { ...p, grams: parseFloat(e.target.value) || 0 };
                setS({ ...s, packaging: next });
              }}
            />
          </div>
        ))}
        <button
          type="button"
          className="text-sm text-primary"
          onClick={() =>
            setS({ ...s, packaging: [...s.packaging, { material_key: 'ldpe_polybag', grams: 8 }] })
          }
        >
          + Add packaging
        </button>
      </div>

      <div>
        <div className="text-sm font-medium text-gray-700 mb-1">Distribution legs</div>
        {s.distribution.map((d, i) => (
          <div key={i} className="flex gap-2 mb-2">
            <select
              className="input flex-1"
              value={d.mode}
              onChange={(e) => {
                const next = [...s.distribution];
                next[i] = { ...d, mode: e.target.value as TransportModeLC };
                setS({ ...s, distribution: next });
              }}
            >
              {['truck', 'rail', 'sea_freight', 'air'].map((k) => (
                <option key={k} value={k}>{humanize(k)}</option>
              ))}
            </select>
            <input
              type="number"
              min={0}
              className="input !w-28"
              placeholder="km"
              value={d.distance_km || ''}
              onChange={(e) => {
                const next = [...s.distribution];
                next[i] = { ...d, distance_km: parseFloat(e.target.value) || 0 };
                setS({ ...s, distribution: next });
              }}
            />
            <button
              type="button"
              className="text-gray-400 hover:text-red-600 px-2"
              onClick={() => setS({ ...s, distribution: s.distribution.filter((_, j) => j !== i) })}
              aria-label="Remove leg"
            >
              ×
            </button>
          </div>
        ))}
        <button
          type="button"
          className="text-sm text-primary"
          onClick={() =>
            setS({ ...s, distribution: [...s.distribution, { mode: 'truck', distance_km: 0 }] })
          }
        >
          + Add leg
        </button>
      </div>

      {error && <div className="text-sm text-red-600">{error}</div>}
      <button
        onClick={save}
        disabled={saving}
        className="shrink-0 whitespace-nowrap bg-primary text-white px-4 py-2 rounded-lg font-medium text-sm hover:bg-primary/90 disabled:opacity-50"
      >
        {saving ? 'Saving…' : 'Save settings'}
      </button>
    </div>
  );
}

const MOVABLE_STAGES = ['yarn_production', 'fabric_production', 'wet_processing', 'assembly'];

function ScenarioCard({ product }: { product: Product }) {
  const fibreKeys = Array.from(
    new Set(
      product.bom_items
        .filter((b) => b.category === 'fiber' && b.material_key)
        .map((b) => b.material_key as string)
    )
  );
  const [swapFrom, setSwapFrom] = useState(fibreKeys[0] ?? '');
  const [swapTo, setSwapTo] = useState('');
  const [moveStage, setMoveStage] = useState('');
  const [moveCountry, setMoveCountry] = useState('BD');
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setError(null);
    try {
      setResult(
        await lifecycleAPI.runScenario(product.id, {
          fibre_swaps: swapFrom && swapTo ? { [swapFrom]: swapTo } : {},
          stage_countries: moveStage ? { [moveStage]: moveCountry } : {},
        })
      );
    } catch {
      setError('Scenario failed.');
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="font-semibold mb-1">Ecodesign scenario</h3>
      <p className="text-xs text-gray-500 mb-3">
        Compare before committing: swap a fibre, or move a stage to a supplier in another country
        (that stage then uses defaults for the new location).
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        <div className="flex gap-2 items-center">
          <select className="input" value={swapFrom} onChange={(e) => setSwapFrom(e.target.value)}>
            <option value="">No fibre swap</option>
            {fibreKeys.map((k) => (
              <option key={k} value={k}>{humanize(k)}</option>
            ))}
          </select>
          <span className="text-gray-400">→</span>
          <select className="input" value={swapTo} onChange={(e) => setSwapTo(e.target.value)}>
            <option value="">—</option>
            {FIBRE_KEYS.filter((k) => k !== swapFrom).map((k) => (
              <option key={k} value={k}>{humanize(k)}</option>
            ))}
          </select>
        </div>
        <div className="flex gap-2 items-center">
          <select className="input" value={moveStage} onChange={(e) => setMoveStage(e.target.value)}>
            <option value="">Keep stage locations</option>
            {MOVABLE_STAGES.map((k) => (
              <option key={k} value={k}>Move {humanize(k)}</option>
            ))}
          </select>
          <span className="text-gray-400">to</span>
          <select className="input" value={moveCountry} onChange={(e) => setMoveCountry(e.target.value)}>
            {Object.entries(COUNTRIES)
              .filter(([k]) => k !== 'EU')
              .map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
          </select>
        </div>
      </div>
      <button
        onClick={run}
        className="mt-3 bg-gray-800 text-white px-4 py-2 rounded-lg text-sm hover:bg-gray-700"
      >
        Compare
      </button>
      {error && <div className="text-sm text-red-600 mt-2">{error}</div>}
      {result && (
        <div className="mt-4 grid grid-cols-3 gap-3 text-center">
          <div className="p-3 bg-gray-50 rounded">
            <div className="text-xs text-gray-500">Current</div>
            <div className="text-lg font-bold">{result.baseline.co2e_kg.toFixed(2)} kg</div>
          </div>
          <div className="p-3 bg-gray-50 rounded">
            <div className="text-xs text-gray-500">Scenario</div>
            <div className="text-lg font-bold">{result.scenario.co2e_kg.toFixed(2)} kg</div>
          </div>
          <div
            className={`p-3 rounded ${
              result.delta_co2e_kg <= 0 ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
            }`}
          >
            <div className="text-xs">Change</div>
            <div className="text-lg font-bold">
              {result.delta_co2e_kg > 0 ? '+' : ''}
              {result.delta_co2e_pct ?? 0}%
            </div>
            <div className="text-xs">
              water {result.delta_water_l > 0 ? '+' : ''}
              {result.delta_water_l.toFixed(0)} L
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
