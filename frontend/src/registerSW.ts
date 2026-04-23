/**
 * Service worker registration entrypoint.
 *
 * vite-plugin-pwa exposes `virtual:pwa-register` at build time. In dev the
 * module may not exist (PWA disabled); we swallow the import failure so the
 * dev server keeps working.
 */
async function register() {
  try {
    const mod = await import('virtual:pwa-register');
    mod.registerSW({ immediate: true });
  } catch {
    // PWA module not available — expected in dev without PWA enabled.
  }
}

if (typeof window !== 'undefined') {
  register();
}

export {};
