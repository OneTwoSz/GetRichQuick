import { useState } from 'react';
import { Copy, RefreshCw, ShieldOff } from 'lucide-react';

// Status + controls for a login-free link (buyer share, job-work request):
// copy, expiry, uses left, issue a new link, revoke.
export default function LinkPanel({
  url,
  expiresAt,
  usesLeft,
  busy,
  onRotate,
  onRevoke,
  note,
}: {
  url: string;
  expiresAt?: string | null;
  usesLeft?: number | null;
  busy?: boolean;
  onRotate: () => void;
  onRevoke: () => void;
  note?: string;
}) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard?.writeText(url).catch(() => undefined);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  const expires = expiresAt ? new Date(expiresAt) : null;
  const daysLeft = expires ? Math.ceil((expires.getTime() - Date.now()) / 86400000) : null;

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm space-y-2">
      {note && <p className="text-xs text-gray-500">{note}</p>}
      <div className="flex gap-2">
        <input readOnly value={url} className="input font-mono text-xs" onFocus={(e) => e.target.select()} />
        <button onClick={copy} className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 text-xs font-medium text-white">
          <Copy className="h-3.5 w-3.5" aria-hidden /> {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
        <span>
          {expires
            ? daysLeft !== null && daysLeft <= 0
              ? 'Expired'
              : `Expires ${expires.toLocaleDateString()} (${daysLeft} day${daysLeft === 1 ? '' : 's'})`
            : 'No expiry'}
        </span>
        {usesLeft !== undefined && usesLeft !== null && <span>{usesLeft} submission{usesLeft === 1 ? '' : 's'} left</span>}
        <span className="flex-1" />
        <button onClick={onRotate} disabled={busy} className="inline-flex items-center gap-1 font-medium text-gray-700 hover:text-gray-900 disabled:opacity-50">
          <RefreshCw className="h-3.5 w-3.5" aria-hidden /> New link
        </button>
        <button onClick={onRevoke} disabled={busy} className="inline-flex items-center gap-1 font-medium text-red-600 hover:text-red-700 disabled:opacity-50">
          <ShieldOff className="h-3.5 w-3.5" aria-hidden /> Revoke
        </button>
      </div>
    </div>
  );
}
