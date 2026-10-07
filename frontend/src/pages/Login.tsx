import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import AuthShell, { authButton, authLabel } from '@/components/AuthShell';
import { apiErrorMessage } from '@/services/api';

// The hosted demo (VITE_DEMO_MODE=true) offers one-tap sign-in to the seeded
// demo factory. These are the public demo credentials from seed_demo.py.
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true';
const DEMO_ACCOUNT = { email: 'demo@greenthread.app', password: 'demo1234' };

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const signIn = async (credentials: { email: string; password: string }) => {
    setError('');
    setLoading(true);

    try {
      await login(credentials);
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Sign-in failed. Check your connection and try again.'));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    signIn({ email, password });
  };

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to your factory workspace.">
      <form className="space-y-5" onSubmit={handleSubmit}>
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}

        <div>
          <label htmlFor="email" className={authLabel}>
            Email address
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input mt-1.5"
          />
        </div>

        <div>
          <div className="flex items-baseline justify-between">
            <label htmlFor="password" className={authLabel}>
              Password
            </label>
            <Link to="/forgot-password" className="text-xs font-medium text-primary hover:text-primary-600">
              Forgot password?
            </Link>
          </div>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input mt-1.5"
          />
        </div>

        <button type="submit" disabled={loading} className={authButton}>
          {loading ? 'Signing in…' : 'Sign in'}
        </button>

        {DEMO_MODE && (
          <>
            <div className="flex items-center gap-3 text-xs text-gray-400">
              <span className="h-px flex-1 bg-gray-200" />
              or
              <span className="h-px flex-1 bg-gray-200" />
            </div>
            <button
              type="button"
              disabled={loading}
              onClick={() => signIn(DEMO_ACCOUNT)}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-primary/30 bg-primary-50 px-4 py-2.5 text-sm font-semibold text-primary-700 transition-colors hover:bg-primary-100 disabled:opacity-50"
            >
              Explore the demo factory
            </button>
            <p className="text-center text-xs text-gray-400">
              Saravana Knits, Tiruppur — sample data, resets periodically.
            </p>
          </>
        )}

        <p className="text-center text-sm text-gray-500">
          New to GreenThread?{' '}
          <Link to="/register" className="font-medium text-primary hover:text-primary-600">
            Create an account
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
