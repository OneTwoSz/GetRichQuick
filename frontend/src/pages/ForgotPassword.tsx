import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import AuthShell, { authButton, authLabel } from '@/components/AuthShell';
import { apiErrorMessage, authAPI } from '@/services/api';

// Request a password-reset link. The answer is the same whether or not the
// email has an account, so this page can't be used to discover accounts.
export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await authAPI.requestPasswordReset(email.trim());
      setSent(true);
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not send the reset link. Try again shortly.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Reset your password" subtitle="We'll email you a link to choose a new one.">
      {sent ? (
        <div className="space-y-5">
          <div className="rounded-lg border border-primary-200 bg-primary-50 px-4 py-3 text-sm text-primary-800">
            If <strong>{email}</strong> has an account, a reset link is on its way. It works for one hour.
          </div>
          <Link to="/login" className="block text-center text-sm font-medium text-primary">
            Back to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
          )}
          <div>
            <label htmlFor="email" className={authLabel}>Email address</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input mt-1.5"
            />
          </div>
          <button type="submit" disabled={busy} className={authButton}>
            {busy ? 'Sending…' : 'Send reset link'}
          </button>
          <p className="text-center text-sm text-gray-500">
            Remembered it?{' '}
            <Link to="/login" className="font-medium text-primary hover:text-primary-600">Sign in</Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}
