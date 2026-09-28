import { FormEvent, useEffect, useState } from 'react';
import { isAxiosError } from 'axios';
import { lifecycleAPI, publicAPI } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import type { PassportStatus, Product } from '@/types';

// Publish and manage the product's Digital Product Passport. Publishing
// runs the automated checks, records a named sign-off, and signs an
// immutable version the QR code resolves to.
export default function PassportPanel({ product }: { product: Product }) {
  const { user } = useAuth();
  const [status, setStatus] = useState<PassportStatus | null>(null);
  const [reviewer, setReviewer] = useState(user?.name ?? '');
  const [note, setNote] = useState('');
  const [discloseNames, setDiscloseNames] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setStatus(null);
    lifecycleAPI.getPassport(product.id).then(setStatus).catch(() => setError('Could not load passport.'));
  }, [product.id]);

  const publish = async (e: FormEvent) => {
    e.preventDefault();
    setPublishing(true);
    setError(null);
    try {
      setStatus(
        await lifecycleAPI.publishPassport(product.id, {
          reviewed_by_name: reviewer.trim(),
          review_note: note.trim() || undefined,
          disclose_supplier_names: discloseNames,
        })
      );
      setConfirm(false);
      setNote('');
    } catch (err) {
      const detail = isAxiosError(err) ? err.response?.data?.detail : null;
      setError(
        detail?.issues
          ? `Blocked by automated checks: ${detail.issues.map((i: { message: string }) => i.message).join('; ')}`
          : 'Publishing failed.'
      );
    } finally {
      setPublishing(false);
    }
  };

  const publicUrl = status?.public_token
    ? `${window.location.origin}/passport/${status.public_token}`
    : null;

  return (
    <div className="space-y-4">
      {status?.public_token && publicUrl && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-semibold mb-3">Live passport</h3>
          <div className="flex flex-col sm:flex-row gap-4 items-start">
            <img
              src={publicAPI.passportQrUrl(status.public_token)}
              alt="Passport QR code"
              className="w-36 h-36 border rounded"
            />
            <div className="flex-1 min-w-0 space-y-2 text-sm">
              <p className="text-gray-600">
                Print this QR on the hangtag or care label. It opens the latest signed version.
              </p>
              <div className="flex gap-2">
                <input readOnly className="input font-mono text-xs" value={publicUrl} />
                <a
                  href={publicUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="bg-primary text-white px-3 py-2 rounded-lg whitespace-nowrap"
                >
                  Open
                </a>
              </div>
              <a
                href={publicAPI.passportQrUrl(status.public_token)}
                download={`${product.sku}-passport-qr.svg`}
                className="text-primary text-xs font-medium"
              >
                Download QR (SVG)
              </a>
            </div>
          </div>
          <table className="w-full text-sm mt-4">
            <thead className="border-b text-xs text-gray-600 text-left">
              <tr>
                <th className="py-2">Version</th>
                <th className="py-2">Published</th>
                <th className="py-2">Reviewed by</th>
                <th className="py-2">Hash</th>
              </tr>
            </thead>
            <tbody>
              {status.versions.map((v) => (
                <tr key={v.version} className="border-b last:border-b-0">
                  <td className="py-2">v{v.version}</td>
                  <td className="py-2">{new Date(v.published_at).toLocaleString()}</td>
                  <td className="py-2">{v.reviewed_by_name}</td>
                  <td className="py-2 font-mono text-xs text-gray-500">{v.payload_hash.slice(0, 12)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form onSubmit={publish} className="bg-white rounded-lg shadow p-6 space-y-3">
        <h3 className="font-semibold">
          {status?.public_token ? 'Publish a new version' : 'Publish the passport'}
        </h3>
        <p className="text-xs text-gray-500">
          Snapshots the current footprint, supply chain and compliance data. Earlier versions stay
          readable; each is signed with your factory key so buyers can detect any change.
        </p>
        <label className="block text-sm">
          <span className="font-medium text-gray-700">Reviewed by *</span>
          <input
            className="input mt-1"
            required
            minLength={2}
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          <span className="font-medium text-gray-700">Review note</span>
          <input
            className="input mt-1"
            placeholder="e.g. Checked against Q2 electricity bills"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={discloseNames}
            onChange={(e) => setDiscloseNames(e.target.checked)}
          />
          Show supplier names publicly (otherwise only stage, city, country and certifications)
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />
          I have reviewed this data and it is accurate to the best of my knowledge
        </label>
        {error && <div className="text-sm text-red-600">{error}</div>}
        <button
          disabled={!confirm || publishing}
          className="bg-primary text-white px-4 py-2 rounded-lg text-sm hover:bg-primary/90 disabled:opacity-50"
        >
          {publishing ? 'Signing…' : 'Sign & publish'}
        </button>
      </form>
    </div>
  );
}
