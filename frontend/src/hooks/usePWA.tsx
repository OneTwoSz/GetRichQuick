/**
 * Thin wrapper around vite-plugin-pwa's registerSW helper.
 *
 * Import once from main.tsx. Exposes `needRefresh` state so we can show the
 * "a new version is available" banner, and a `refresh()` function to apply.
 *
 * If the virtual:pwa-register module isn't available (dev server without
 * PWA enabled), this degrades to a no-op rather than throwing.
 */
import { useEffect, useState } from 'react';

export function usePWA() {
  const [needRefresh, setNeedRefresh] = useState(false);
  const [updateFn, setUpdateFn] = useState<(() => Promise<void>) | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Dynamic import so a non-PWA dev build doesn't explode at parse time.
    import('virtual:pwa-register')
      .then(({ registerSW }) => {
        if (cancelled) return;
        const update = registerSW({
          onNeedRefresh() {
            setNeedRefresh(true);
          },
          onRegisterError(err: unknown) {
            console.warn('SW registration failed', err);
          },
        });
        setUpdateFn(() => async () => {
          await update(true);
        });
      })
      .catch(() => {
        /* PWA not available in this build — fine in dev */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return {
    needRefresh,
    refresh: updateFn ?? (async () => {}),
    dismiss: () => setNeedRefresh(false),
  };
}
