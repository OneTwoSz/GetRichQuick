import { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '@/services/api';
import type { User, LoginCredentials, RegisterData } from '@/types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
}

const NO_AUTOLOGIN = 'gt-signed-out'; // dev: don't auto-login after an explicit sign-out

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // React StrictMode runs effects twice in development; without this guard
  // the dev auto-login would open two sessions.
  const booted = useRef(false);

  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    const bootstrap = async () => {
      // Tokens used to live in localStorage; sessions are httpOnly cookies
      // now, so drop any leftover.
      try {
        localStorage.removeItem('token');
      } catch {
        // storage blocked — nothing to clean
      }

      let me: User | null = null;
      try {
        me = await authAPI.getMe();
      } catch {
        me = null;
      }

      // Dev convenience: in a Vite dev build with no session, silently sign
      // in as the demo user — unless you signed out in this tab. Production
      // builds skip this entirely.
      if (!me && import.meta.env.DEV && sessionStorage.getItem(NO_AUTOLOGIN) !== '1') {
        try {
          me = await authAPI.login({ email: 'demo@greenthread.app', password: 'demo1234' });
          // eslint-disable-next-line no-console
          console.info('[dev] auto-logged in as demo@greenthread.app');
        } catch (err) {
          // eslint-disable-next-line no-console
          console.warn('[dev] auto-login failed:', err);
        }
      }

      setUser(me);
      setLoading(false);
    };

    bootstrap();
  }, []);

  const login = async (credentials: LoginCredentials) => {
    setUser(await authAPI.login(credentials));
    sessionStorage.removeItem(NO_AUTOLOGIN);
    navigate('/');
  };

  const register = async (data: RegisterData) => {
    setUser(await authAPI.register(data)); // registering signs you in
    navigate('/');
  };

  const logout = async () => {
    await authAPI.logout().catch(() => undefined);
    sessionStorage.setItem(NO_AUTOLOGIN, '1');
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
