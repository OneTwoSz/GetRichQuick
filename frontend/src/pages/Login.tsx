import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import AuthShell, { authButton, authLabel } from '@/components/AuthShell';

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login({ email, password });
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Login failed';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
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
          <label htmlFor="password" className={authLabel}>
            Password
          </label>
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
