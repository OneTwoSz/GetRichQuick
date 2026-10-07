import { FormEvent, useEffect, useState } from 'react';
import { LogOut, Monitor, Smartphone } from 'lucide-react';
import { apiErrorMessage, authAPI } from '@/services/api';
import type { SessionInfo } from '@/types';

// Change password, see signed-in devices, sign them out.
export default function SecuritySettings() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => authAPI.sessions().then(setSessions).catch(() => undefined);
  useEffect(() => {
    load();
  }, []);

  const changePassword = async (e: FormEvent) => {
    e.preventDefault();
    if (next !== confirm) {
      setMessage({ ok: false, text: 'The new passwords don’t match.' });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      await authAPI.changePassword(current, next);
      setCurrent('');
      setNext('');
      setConfirm('');
      setMessage({ ok: true, text: 'Password changed. Other devices have been signed out.' });
      load();
    } catch (err) {
      setMessage({ ok: false, text: apiErrorMessage(err, 'Could not change the password.') });
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (s: SessionInfo) => {
    await authAPI.revokeSession(s.id);
    load();
  };

  const signOutEverywhere = async () => {
    if (!window.confirm('Sign out on every device, including this one?')) return;
    await authAPI.logoutAll();
    window.location.href = '/login';
  };

  const device = (ua?: string | null) => {
    if (!ua) return 'Unknown device';
    const mobile = /Android|iPhone|iPad|Mobile/i.test(ua);
    const browser = /Edg\//.test(ua) ? 'Edge' : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : 'Browser';
    const os = /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Mac OS/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : '';
    return { label: `${browser}${os ? ` on ${os}` : ''}`, mobile };
  };

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-6 border-b border-gray-200">
        <h2 className="text-xl font-semibold text-gray-900">Security</h2>
      </div>
      <div className="grid gap-8 p-6 lg:grid-cols-2">
        <form onSubmit={changePassword} className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Change password</h3>
          {message && (
            <div className={`rounded-lg px-3 py-2 text-sm ${message.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
              {message.text}
            </div>
          )}
          <input type="password" autoComplete="current-password" placeholder="Current password" required
            value={current} onChange={(e) => setCurrent(e.target.value)} className="input" />
          <input type="password" autoComplete="new-password" placeholder="New password (8+ characters)" required minLength={8}
            value={next} onChange={(e) => setNext(e.target.value)} className="input" />
          <input type="password" autoComplete="new-password" placeholder="Confirm new password" required minLength={8}
            value={confirm} onChange={(e) => setConfirm(e.target.value)} className="input" />
          <button disabled={busy} className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-600 disabled:opacity-50">
            {busy ? 'Saving…' : 'Change password'}
          </button>
        </form>

        <div>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-900">Signed-in devices</h3>
            <button onClick={signOutEverywhere} className="inline-flex items-center gap-1 text-xs font-medium text-red-600 hover:text-red-700">
              <LogOut className="h-3.5 w-3.5" aria-hidden /> Sign out everywhere
            </button>
          </div>
          <ul className="divide-y rounded-lg border border-gray-200">
            {sessions.map((s) => {
              const d = device(s.user_agent);
              const info = typeof d === 'string' ? { label: d, mobile: false } : d;
              const Icon = info.mobile ? Smartphone : Monitor;
              return (
                <li key={s.id} className="flex items-center gap-3 px-3 py-2.5 text-sm">
                  <Icon className="h-4 w-4 shrink-0 text-gray-400" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-gray-900">
                      {info.label} {s.current && <span className="ml-1 rounded bg-primary-50 px-1.5 py-0.5 text-[11px] text-primary-700">This device</span>}
                    </div>
                    <div className="text-xs text-gray-500">
                      Last active {new Date(s.last_seen_at).toLocaleString()}
                      {s.ip_address ? ` · ${s.ip_address}` : ''}
                    </div>
                  </div>
                  {!s.current && (
                    <button onClick={() => revoke(s)} className="text-xs font-medium text-red-600 hover:text-red-700">
                      Sign out
                    </button>
                  )}
                </li>
              );
            })}
            {sessions.length === 0 && <li className="px-3 py-2.5 text-sm text-gray-500">Loading…</li>}
          </ul>
        </div>
      </div>
    </div>
  );
}
