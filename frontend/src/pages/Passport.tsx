import Logo from '@/components/Logo';
import { ThemeIconButton } from '@/components/ThemeToggle';
import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { publicAPI } from '@/services/api';
import type { PublicPassport } from '@/types';
import { QualityMixBar, StageBreakdown } from '@/components/StageBreakdown';
import {
  BOUNDARY_LABELS,
  COUNTRIES,
  SUPPLY_STAGE_LABELS,
  humanize,
} from '@/components/lifecycleLabels';

// Public Digital Product Passport — what the QR code on the garment opens.
// No login. Every load re-verifies the signed snapshot server-side.
export default function Passport() {
  const { token } = useParams<{ token: string }>();
  const [params] = useSearchParams();
  const version = params.get('version') ? Number(params.get('version')) : undefined;
  const [data, setData] = useState<PublicPassport | null>(null);
  const [error, setError] = useState(false);
  const [showProof, setShowProof] = useState(false);

  useEffect(() => {
    if (!token) return;
    setData(null);
    publicAPI.getPassport(token, version).then(setData).catch(() => setError(true));
  }, [token, version]);

  if (error) {
    return (
      <Shell>
        <div className="bg-white rounded-lg shadow p-6 text-sm text-red-600">
          This passport could not be found.
        </div>
      </Shell>
    );
  }
  if (!data) {
    return (
      <Shell>
        <div className="text-gray-500">Loading…</div>
      </Shell>
    );
  }

  const p = data.payload;
  const fp = p.footprint;
  const verified = data.verification.verified;
  const latest = data.versions[0]?.version;

  return (
    <Shell>
      <div
        className={`rounded-lg p-4 text-sm flex gap-3 items-start ${
          verified ? 'bg-green-50 border border-green-200 text-green-900' : 'bg-red-50 border border-red-200 text-red-900'
        }`}
      >
        <span className="text-xl leading-none">{verified ? '✓' : '✕'}</span>
        <div>
          {verified ? (
            <>
              <div className="font-semibold">Verified passport</div>
              Signed by {p.manufacturer.name} on{' '}
              {new Date(data.published_at).toLocaleDateString()} and unchanged since.
            </>
          ) : (
            <>
              <div className="font-semibold">Verification failed</div>
              This content does not match what the manufacturer signed. Do not rely on it.
            </>
          )}
          {latest !== undefined && data.version !== latest && (
            <div className="mt-1">
              You are viewing version {data.version}.{' '}
              <Link to={`/passport/${token}`} className="underline">See the latest (v{latest})</Link>
            </div>
          )}
        </div>
      </div>

      <section className="bg-white rounded-lg shadow p-5">
        <div className="text-xs font-mono text-gray-500">{p.product.sku}</div>
        <h1 className="text-2xl font-bold">{p.product.name}</h1>
        {p.product.description && <p className="text-sm text-gray-600 mt-1">{p.product.description}</p>}
        <div className="flex flex-wrap gap-2 mt-3">
          {p.composition.map((c) => (
            <span key={c.material} className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-700">
              {c.share_pct !== null ? `${c.share_pct}% ` : ''}
              {c.material}
            </span>
          ))}
        </div>
        <div className="text-sm text-gray-600 mt-3">
          Made by <span className="font-medium">{p.manufacturer.name}</span> · {p.manufacturer.location},{' '}
          {COUNTRIES[p.manufacturer.country] ?? p.manufacturer.country}
        </div>
      </section>

      <section className="bg-white rounded-lg shadow p-5">
        <h2 className="font-semibold">Environmental footprint</h2>
        <p className="text-xs text-gray-500 mb-4">
          Per {fp.functional_unit} · {BOUNDARY_LABELS[fp.boundary]}
        </p>
        <div className="grid grid-cols-3 gap-3 mb-5 text-center">
          <Big value={fp.co2e_kg.toFixed(2)} unit="kg CO₂e" label="Carbon" />
          <Big value={fp.water_l.toFixed(0)} unit="litres" label="Water" />
          <Big value={`${fp.primary_data_share_pct.toFixed(0)}%`} unit="primary data" label="Measured at source" />
        </div>
        <div className="mb-5">
          <div className="text-xs font-medium text-gray-600 mb-1">How the numbers were obtained</div>
          <QualityMixBar mix={fp.quality_mix} />
        </div>
        <StageBreakdown stages={fp.stages} />
        {fp.excluded_stages.length > 0 && (
          <p className="text-xs text-gray-500 mt-4">
            Not included: {fp.excluded_stages.map(humanize).join(', ')}.
          </p>
        )}
      </section>

      <section className="bg-white rounded-lg shadow p-5">
        <h2 className="font-semibold mb-3">Supply chain</h2>
        <ol className="relative border-l-2 border-primary-100 ml-2 space-y-4">
          {p.supply_chain.map((s) => (
            <li key={s.stage} className="ml-4">
              <span className="absolute -left-[7px] mt-1.5 w-3 h-3 rounded-full bg-primary" />
              <div className="text-sm font-medium">{SUPPLY_STAGE_LABELS[s.stage]}</div>
              <div className="text-xs text-gray-600">
                {s.facility ? `${s.facility} · ` : ''}
                {s.city ? `${s.city}, ` : ''}
                {COUNTRIES[s.country] ?? s.country} · Tier {s.tier}
              </div>
              {s.certifications.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {s.certifications.map((c) => (
                    <span key={c} className="text-[11px] px-1.5 py-0.5 rounded bg-green-50 text-green-700">
                      {c}
                    </span>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ol>
      </section>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <section className="bg-white rounded-lg shadow p-5 text-sm space-y-1">
          <h2 className="font-semibold mb-2">Circularity</h2>
          <Row label="Recycled content" value={`${p.circularity.recycled_content_pct}%`} />
          <Row label="Cutting waste" value={`${p.circularity.cutting_waste_pct}%`} />
          {p.circularity.cutting_waste_destination && (
            <Row label="Cutting waste goes to" value={humanize(p.circularity.cutting_waste_destination)} />
          )}
          <Row label="End-of-life scenario" value={humanize(p.circularity.end_of_life_scenario)} />
        </section>
        <section className="bg-white rounded-lg shadow p-5 text-sm space-y-1">
          <h2 className="font-semibold mb-2">Chemicals</h2>
          <Row label="Process chemicals traced" value={`${p.chemical_compliance.chemicals_traced}`} />
          <Row label="ZDHC MRSL conformant" value={`${p.chemical_compliance.zdhc_mrsl_conformant}`} />
          <Row label="REACH compliant" value={`${p.chemical_compliance.reach_compliant}`} />
        </section>
      </div>

      {p.product.care_instructions && (
        <section className="bg-white rounded-lg shadow p-5 text-sm">
          <h2 className="font-semibold mb-1">Care</h2>
          <p className="text-gray-700">{p.product.care_instructions}</p>
        </section>
      )}

      <section className="bg-white rounded-lg shadow p-5 text-sm">
        <button onClick={() => setShowProof((s) => !s)} className="font-semibold w-full text-left">
          Verification details {showProof ? '▴' : '▾'}
        </button>
        {showProof && (
          <div className="mt-3 space-y-2 text-xs text-gray-700">
            <Row label="Reviewed by" value={p.verification.reviewed_by} />
            {p.verification.review_note && <Row label="Review note" value={p.verification.review_note} />}
            <Row
              label="Automated checks"
              value={`${p.verification.automated_checks.errors} errors, ${p.verification.automated_checks.warnings} warnings`}
            />
            <Row label="Signature" value={`${data.algorithm} · ${data.verification.signature_valid ? 'valid' : 'INVALID'}`} />
            <Row label="Content hash" value={data.verification.hash_matches ? 'matches' : 'DOES NOT MATCH'} />
            <div className="font-mono break-all bg-gray-50 rounded p-2">{data.payload_hash}</div>
            <p className="text-gray-500">{fp.methodology}</p>
            <p className="text-gray-500">
              Stages marked “Default factor” use disclosed industry-average factors, not
              measurements from this product&apos;s supply chain.
            </p>
            {data.versions.length > 1 && (
              <div>
                Versions:{' '}
                {data.versions.map((v) => (
                  <Link key={v.version} to={`/passport/${token}?version=${v.version}`} className="underline mr-2">
                    v{v.version}
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}
      </section>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="sticky top-0 z-10 border-b border-gray-200 bg-white/80 backdrop-blur-md">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <Logo />
          <span className="flex items-center gap-2 text-xs text-gray-500">Digital Product Passport<ThemeIconButton /></span>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 py-6 space-y-4">{children}</main>
    </div>
  );
}

function Big({ value, unit, label }: { value: string; unit: string; label: string }) {
  return (
    <div className="p-3 rounded bg-primary-50">
      <div className="text-2xl font-bold text-primary">{value}</div>
      <div className="text-xs text-gray-600">{unit}</div>
      <div className="text-[11px] text-gray-500 mt-1">{label}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-right">{value}</span>
    </div>
  );
}
