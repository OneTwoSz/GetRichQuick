import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '@/services/api';
import type { User, LoginCredentials, RegisterData } from '@/types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const bootstrap = async () => {
      let token = localStorage.getItem('token');

      // Dev convenience: when running `npm run dev` we don't want to click
      // through the login screen every reload. If no token is present and
      // we're in a Vite dev build, silently log in as the demo user. The
      // real auth flow stays intact — production builds (import.meta.env.DEV
      // === false) skip this entirely.
      if (!token && import.meta.env.DEV) {
        try {
          const resp = await authAPI.login({
            email: 'demo@greenthread.app',
            password: 'demo1234',
          });
          token = resp.access_token;
          localStorage.setItem('token', token);
          // eslint-disable-next-line no-console
          console.info('[dev] auto-logged in as demo@greenthread.app');
        } catch (err) {
          // Probably means the backend isn't up or the demo user wasn't
          // seeded. Fall through to the login screen so the dev sees why.
          // eslint-disable-next-line no-console
          console.warn('[dev] auto-login failed:', err);
        }
      }

      if (token) {
        try {
          const me = await authAPI.getMe();
          setUser(me);
        } catch {
          localStorage.removeItem('token');
        }
      }
      setLoading(false);
    };

    bootstrap();
  }, []);

  const login = async (credentials: LoginCredentials) => {
    const response = await authAPI.login(credentials);
    localStorage.setItem('token', response.access_token);
    const user = await authAPI.getMe();
    setUser(user);
    navigate('/');
  };

  const register = async (data: RegisterData) => {
    await authAPI.register(data);
    await login({ email: data.email, password: data.password });
  };

  const logout = () => {
    localStorage.removeItem('token');
    setUser(null);
    navigate('/login');
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
