/**
 * Public verify page — no auth required.
 *
 * A buyer follows a link from a signed sustainability PDF, e.g.
 *   https://greenthread.app/verify/1234
 *
 * We fetch GET /api/verify/:reportId and show three checks:
 *   1. Signature valid — the report's payload hash was signed by this
 *      factory's key and the signature is mathematically valid.
 *   2. Merkle anchor — the hash is included in a daily Merkle root we
 *      committed to OpenTimestamps (if the daily job has already run).
 *   3. Bitcoin attestation — the OTS proof has been upgraded with a Bitcoin
 *      attestation (takes a few hours after submission).
 *
 * Deliberately minimalist: no nav, no auth, no tracking. Buyers land, see a
 * green tick, leave. The PDF itself is not exposed here.
 */
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

interface VerifyResponse {
  report_id: number;
  report_type: string | null;
  date_from: string;
  date_to: string;
  created_at: string;
  factory: { name: string | null; location: string | null };
  payload_hash: string | null;
  signature: null | {
    algorithm: string;
    provider: string;
    signed_at: string;
    signature_b64: string;
    public_key_pem: string;
  };
  signature_valid: boolean;
  merkle_anchor: null | {
    anchor_date: string;
    merkle_root_hex: string;
    leaf_count: number;
    inclusion_proof: string[] | null;
    ots_submitted_at: string | null;
    ots_upgraded_at: string | null;
    ots_proof_available: boolean;
  };
}

function StatusRow({
  ok,
  pending,
  label,
  detail,
}: {
  ok: boolean;
  pending?: boolean;
  label: string;
  detail?: string;
}) {
  let color = 'text-red-700 bg-red-50 border-red-200';
  let symbol = '✗';
  if (pending) {
    color = 'text-gray-700 bg-gray-50 border-gray-200';
    symbol = '…';
  } else if (ok) {
    color = 'text-green-800 bg-green-50 border-green-200';
    symbol = '✓';
  }
  return (
    <div className={`border rounded-lg px-4 py-3 flex items-start gap-3 ${color}`}>
      <div className="text-xl leading-none font-bold w-6 text-center">{symbol}</div>
      <div>
        <div className="font-medium">{label}</div>
        {detail && <div className="text-xs mt-1 opacity-80">{detail}</div>}
      </div>
    </div>
  );
}

export default function Verify() {
  const { reportId } = useParams<{ reportId: string }>();
  const [data, setData] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!reportId) return;
    setLoading(true);
    axios
      .get<VerifyResponse>(`${API_URL}/verify/${reportId}`)
      .then((res) => setData(res.data))
      .catch((err) => setError(err?.response?.data?.detail || err.message || 'Failed to verify'))
      .finally(() => setLoading(false));
  }, [reportId]);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-3xl mx-auto">
          <div className="text-xl font-bold text-primary">GreenThread</div>
          <div className="text-sm text-gray-600">Report verification</div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        {loading && <div className="text-gray-600">Verifying report…</div>}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-4">
            {error}
          </div>
        )}

        {data && (
          <>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="text-xs uppercase tracking-wide text-gray-500">Report</div>
              <div className="text-2xl font-semibold text-gray-900 mt-1">
                #{data.report_id} — {data.factory.name ?? 'Unknown factory'}
              </div>
              <div className="text-sm text-gray-600">
                {data.factory.location} · {data.report_type ?? '—'}
              </div>
              <div className="text-sm text-gray-600 mt-2">
                Coverage: {new Date(data.date_from).toLocaleDateString()} →{' '}
                {new Date(data.date_to).toLocaleDateString()}
              </div>
            </div>

            <div className="space-y-3">
              <StatusRow
                ok={data.signature_valid}
                label={data.signature_valid ? 'Signature valid' : 'Signature invalid or missing'}
                detail={
                  data.signature
                    ? `${data.signature.algorithm} via ${data.signature.provider} — signed ${new Date(
                        data.signature.signed_at,
                      ).toLocaleString()}`
                    : 'No signature on file for this report.'
                }
              />

              <StatusRow
                ok={!!data.merkle_anchor && Array.isArray(data.merkle_anchor.inclusion_proof)}
                pending={!data.merkle_anchor}
                label={
                  data.merkle_anchor
                    ? 'Included in daily Merkle anchor'
                    : 'Awaiting daily Merkle anchor'
                }
                detail={
                  data.merkle_anchor
                    ? `Root ${data.merkle_anchor.merkle_root_hex.slice(0, 24)}…  (${data.merkle_anchor.leaf_count} reports in batch)`
                    : 'The daily anchoring job has not yet run for this report.'
                }
              />

              <StatusRow
                ok={!!data.merkle_anchor?.ots_upgraded_at}
                pending={!!data.merkle_anchor && !data.merkle_anchor.ots_upgraded_at}
                label={
                  data.merkle_anchor?.ots_upgraded_at
                    ? 'Bitcoin-attested (OpenTimestamps)'
                    : data.merkle_anchor?.ots_submitted_at
                    ? 'Bitcoin attestation pending'
                    : 'Not yet submitted to OpenTimestamps'
                }
                detail={
                  data.merkle_anchor?.ots_upgraded_at
                    ? `Attested ${new Date(data.merkle_anchor.ots_upgraded_at).toLocaleString()}`
                    : data.merkle_anchor?.ots_submitted_at
                    ? `Submitted ${new Date(data.merkle_anchor.ots_submitted_at).toLocaleString()} — attestations normally land within a few hours.`
                    : undefined
                }
              />
            </div>

            <details className="bg-white rounded-lg border border-gray-200 p-4">
              <summary className="cursor-pointer text-sm font-medium text-gray-700">
                Technical details
              </summary>
              <dl className="mt-3 text-xs text-gray-700 space-y-2">
                <div>
                  <dt className="text-gray-500">Payload hash (SHA-256)</dt>
                  <dd className="font-mono break-all">{data.payload_hash}</dd>
                </div>
                {data.signature && (
                  <>
                    <div>
                      <dt className="text-gray-500">Signature (base64)</dt>
                      <dd className="font-mono break-all">{data.signature.signature_b64}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Public key</dt>
                      <dd className="font-mono break-all whitespace-pre-wrap">
                        {data.signature.public_key_pem}
                      </dd>
                    </div>
                  </>
                )}
                {data.merkle_anchor && (
                  <div>
                    <dt className="text-gray-500">Merkle inclusion proof</dt>
                    <dd className="font-mono break-all">
                      {JSON.stringify(data.merkle_anchor.inclusion_proof)}
                    </dd>
                  </div>
                )}
              </dl>
            </details>
          </>
        )}
      </main>
    </div>
  );
}
