/**
 * Offline/queue status pill for the top bar.
 *
 * Shows one of three states:
 *   - Online & empty queue: hidden (zero UI chrome when things are normal)
 *   - Online + N pending writes: amber "Syncing (N)" pill with a retry button
 *   - Offline: gray "Offline" pill. If the queue has pending writes, they
 *     flush automatically when navigator comes back online.
 */
import { useEffect, useState } from 'react';
import { drainQueue, subscribe } from '@/services/offlineQueue';

export default function OfflineStatus() {
  const [online, setOnline] = useState<boolean>(
    typeof navigator !== 'undefined' ? navigator.onLine : true,
  );
  const [pending, setPending] = useState<number>(0);
  const [flushing, setFlushing] = useState(false);

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    const unsub = subscribe(setPending);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
      unsub();
    };
  }, []);

  const handleFlush = async () => {
    setFlushing(true);
    try {
      await drainQueue();
    } finally {
      setFlushing(false);
    }
  };

  if (online && pending === 0) return null;

  if (!online) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200">
        <span className="w-1.5 h-1.5 rounded-full bg-gray-500" />
        Offline{pending > 0 ? ` · ${pending} queued` : ''}
      </span>
    );
  }

  return (
    <button
      onClick={handleFlush}
      disabled={flushing}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100 disabled:opacity-60"
      title="Retry pending uploads"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
      {flushing ? 'Syncing…' : `Syncing (${pending})`}
    </button>
  );
}
