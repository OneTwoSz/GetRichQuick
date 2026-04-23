/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

// Ambient declaration for dynamic import of the PWA register module; keeps
// TS happy in dev builds where the virtual module may not exist.
declare module 'virtual:pwa-register' {
  export interface RegisterSWOptions {
    immediate?: boolean;
    onNeedRefresh?: () => void;
    onOfflineReady?: () => void;
    onRegistered?: (registration: ServiceWorkerRegistration | undefined) => void;
    onRegisterError?: (error: unknown) => void;
  }
  export function registerSW(
    options?: RegisterSWOptions,
  ): (reloadPage?: boolean) => Promise<void>;
}
