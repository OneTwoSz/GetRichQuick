import { FormEvent, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import AuthShell, { authButton, authLabel } from '@/components/AuthShell';
import { apiErrorMessage, authAPI } from '@/services/api';

// Choose a new password from an emailed reset link (?token=...). Success
// signs out every device, so the user signs in fresh afterwards.
export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setError('The two passwords don’t match.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await authAPI.confirmPasswordReset(token, password);
      setDone(true);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not reset the password.'));
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <AuthShell title="Reset link missing" subtitle="Open the link from your email, or request a new one.">
        <Link to="/forgot-password" className={authButton}>Request a new link</Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Choose a new password" subtitle="At least 8 characters. You'll be signed out everywhere.">
      {done ? (
        <div className="space-y-5">
          <div className="rounded-lg border border-primary-200 bg-primary-50 px-4 py-3 text-sm text-primary-800">
            Password changed. Sign in with your new password.
          </div>
          <Link to="/login" className={authButton}>Sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}{' '}
              {/expired|invalid/i.test(error) && (
                <Link to="/forgot-password" className="font-medium underline">Request a new link</Link>
              )}
            </div>
          )}
          <div>
            <label htmlFor="password" className={authLabel}>New password</label>
            <input id="password" type="password" autoComplete="new-password" required minLength={8}
              value={password} onChange={(e) => setPassword(e.target.value)} className="input mt-1.5" />
          </div>
          <div>
            <label htmlFor="confirm" className={authLabel}>Confirm new password</label>
            <input id="confirm" type="password" autoComplete="new-password" required minLength={8}
              value={confirm} onChange={(e) => setConfirm(e.target.value)} className="input mt-1.5" />
          </div>
          <button type="submit" disabled={busy} className={authButton}>
            {busy ? 'Saving…' : 'Set new password'}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
