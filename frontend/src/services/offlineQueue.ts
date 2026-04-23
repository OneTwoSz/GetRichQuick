/**
 * Offline write queue.
 *
 * When the factory's phone has no internet (and a Tiruppur dyehouse does NOT
 * have reliable internet — plan for two hours of daily downtime in summer),
 * data-entry pages enqueue their writes here instead of calling the API
 * directly. When we come back online we drain the queue in FIFO order.
 *
 * Why IndexedDB not localStorage: localStorage tops out at ~5 MB and blocks
 * the main thread. IndexedDB gives us proper transactional writes and ~50 MB
 * on mobile — enough for multi-day queues of production rows + photos.
 *
 * A drained write that returns 4xx (business error) is deleted; network /
 * 5xx errors leave it in the queue for the next retry pass.
 */
import { openDB, type DBSchema, type IDBPDatabase } from 'idb';
import api from './api';

interface QueuedWrite {
  id: string;
  method: 'POST' | 'PUT' | 'DELETE';
  url: string;
  body?: unknown;
  createdAt: number;
  attempts: number;
  lastError?: string;
}

interface GTSchema extends DBSchema {
  outbox: {
    key: string;
    value: QueuedWrite;
    indexes: { 'by-createdAt': number };
  };
}

let dbPromise: Promise<IDBPDatabase<GTSchema>> | null = null;

function getDB(): Promise<IDBPDatabase<GTSchema>> {
  if (!dbPromise) {
    dbPromise = openDB<GTSchema>('greenthread', 1, {
      upgrade(db) {
        const store = db.createObjectStore('outbox', { keyPath: 'id' });
        store.createIndex('by-createdAt', 'createdAt');
      },
    });
  }
  return dbPromise;
}

function uuid(): string {
  // crypto.randomUUID is widely available; fall back for older iOS Safari.
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export async function enqueueWrite(
  method: QueuedWrite['method'],
  url: string,
  body?: unknown,
): Promise<string> {
  const db = await getDB();
  const id = uuid();
  await db.put('outbox', {
    id,
    method,
    url,
    body,
    createdAt: Date.now(),
    attempts: 0,
  });
  notifyChange();
  return id;
}

export async function listQueued(): Promise<QueuedWrite[]> {
  const db = await getDB();
  return db.getAllFromIndex('outbox', 'by-createdAt');
}

export async function queueSize(): Promise<number> {
  const db = await getDB();
  return db.count('outbox');
}

export async function clearQueued(id: string): Promise<void> {
  const db = await getDB();
  await db.delete('outbox', id);
  notifyChange();
}

/**
 * Drain the queue. Returns a summary of outcomes.
 *
 * This is safe to call frequently — if we're offline the first item will
 * fail fast and we bail.
 */
export async function drainQueue(): Promise<{
  sent: number;
  failed: number;
  remaining: number;
}> {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return { sent: 0, failed: 0, remaining: await queueSize() };
  }
  const db = await getDB();
  const items = await db.getAllFromIndex('outbox', 'by-createdAt');
  let sent = 0;
  let failed = 0;
  for (const item of items) {
    try {
      await api.request({
        method: item.method,
        url: item.url,
        data: item.body,
      });
      await db.delete('outbox', item.id);
      sent += 1;
    } catch (err: any) {
      const status = err?.response?.status;
      const isBusiness = typeof status === 'number' && status >= 400 && status < 500;
      if (isBusiness) {
        // 4xx means the server rejected the payload — retrying won't help.
        // Drop it rather than block every subsequent write forever. The row
        // that failed is logged so the user can re-enter by hand.
        console.warn('offlineQueue: dropping 4xx item', item, err?.response?.data);
        await db.delete('outbox', item.id);
      } else {
        // Network/5xx — keep in queue.
        item.attempts += 1;
        item.lastError = err?.message ?? 'unknown';
        await db.put('outbox', item);
      }
      failed += 1;
      // If we've hit a network error, bail now; the rest will also fail and
      // we're wasting battery.
      if (!status) break;
    }
  }
  notifyChange();
  return { sent, failed, remaining: await queueSize() };
}

// ------- change notification ------------------------------------------------

type Listener = (size: number) => void;
const listeners = new Set<Listener>();

export function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  queueSize().then((size) => fn(size));
  return () => {
    listeners.delete(fn);
  };
}

async function notifyChange() {
  const size = await queueSize();
  for (const fn of listeners) fn(size);
}

// ------- auto-drain on reconnect -------------------------------------------

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    drainQueue().catch((err) => console.warn('drainQueue on online failed', err));
  });
  // Opportunistically drain on load, in case writes are queued from a prior
  // session and we're currently online.
  setTimeout(() => drainQueue().catch(() => {}), 1500);
}
