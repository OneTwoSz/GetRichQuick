import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ClipboardList,
  FileText,
  Layers,
  LayoutDashboard,
  LogOut,
  LucideIcon,
  Network,
  PackageCheck,
  Settings,
  ShieldCheck,
  Shirt,
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import OfflineStatus from '@/components/OfflineStatus';
import Logo from '@/components/Logo';
import { ThemeIconButton, ThemeSegmented } from '@/components/ThemeToggle';

interface LayoutProps {
  children: ReactNode;
}

interface NavItem {
  name: string;
  path: string;
  Icon: LucideIcon;
}

// Batches are the primary data-entry action (phase 2) — one lot, one dye
// bath; orders attach to the batch afterwards.
const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  { label: 'Overview', items: [{ name: 'Dashboard', path: '/', Icon: LayoutDashboard }] },
  {
    label: 'Production',
    items: [
      { name: 'Batches', path: '/batches', Icon: Layers },
      { name: 'Orders', path: '/orders', Icon: PackageCheck },
      { name: 'Production data', path: '/production', Icon: ClipboardList },
    ],
  },
  {
    label: 'Products',
    items: [
      { name: 'Products', path: '/products', Icon: Shirt },
      { name: 'Suppliers', path: '/suppliers', Icon: Network },
    ],
  },
  {
    label: 'Trust',
    items: [
      { name: 'Compliance', path: '/compliance', Icon: ShieldCheck },
      { name: 'Reports', path: '/reports', Icon: FileText },
    ],
  },
];
const SETTINGS: NavItem = { name: 'Settings', path: '/settings', Icon: Settings };
const ALL_ITEMS = [...NAV_GROUPS.flatMap((g) => g.items), SETTINGS];

// The mobile bottom bar fits ~5 items; keep the factory-floor essentials.
const MOBILE_PATHS = ['/', '/batches', '/orders', '/products', '/reports'];

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const { user, logout } = useAuth();

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);
  const current = ALL_ITEMS.find((i) => isActive(i.path));
  const initials = (user?.name ?? '?')
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  const navLink = ({ name, path, Icon }: NavItem) => {
    const active = isActive(path);
    return (
      <Link
        key={path}
        to={path}
        className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
          active ? 'bg-primary-50 text-primary-700' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
        }`}
      >
        {active && <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-primary" />}
        <Icon
          className={`h-[18px] w-[18px] ${active ? 'text-primary' : 'text-gray-400 group-hover:text-gray-600'}`}
          strokeWidth={1.8}
          aria-hidden
        />
        {name}
      </Link>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar — desktop */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col border-r border-gray-200 bg-white md:flex">
        <div className="flex h-16 items-center px-5">
          <Link to="/" aria-label="GreenThread home">
            <Logo />
          </Link>
        </div>
        <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                {group.label}
              </div>
              <div className="space-y-0.5">{group.items.map(navLink)}</div>
            </div>
          ))}
        </nav>
        <div className="space-y-3 border-t border-gray-200 p-3">
          {navLink(SETTINGS)}
          <ThemeSegmented />
          <div className="flex items-center gap-3 rounded-lg px-2 py-1.5">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
              {initials}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-gray-900">{user?.name}</div>
              <div className="truncate text-xs text-gray-500">{user?.email}</div>
            </div>
            <button
              onClick={logout}
              aria-label="Log out"
              title="Log out"
              className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-red-600"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <div className="md:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-10 border-b border-gray-200 bg-gray-50/80 backdrop-blur-md">
          <div className="flex h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
            <div className="flex items-center gap-3">
              <span className="md:hidden">
                <Logo withWordmark={false} />
              </span>
              <span className="text-sm font-medium text-gray-900">{current?.name ?? 'GreenThread'}</span>
            </div>
            <div className="flex items-center gap-2">
              <OfflineStatus />
              <span className="md:hidden">
                <ThemeIconButton />
              </span>
              <button
                onClick={logout}
                aria-label="Log out"
                className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-red-600 md:hidden"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </header>

        <main className="px-4 pb-28 pt-6 sm:px-6 md:pb-10 lg:px-8">
          <div className="mx-auto max-w-7xl">{children}</div>
        </main>
      </div>

      {/* Bottom tab bar — mobile */}
      <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-gray-200 bg-white/90 backdrop-blur-md md:hidden">
        <div className="flex justify-around pb-[env(safe-area-inset-bottom)]">
          {ALL_ITEMS.filter((i) => MOBILE_PATHS.includes(i.path)).map(({ name, path, Icon }) => {
            const active = isActive(path);
            return (
              <Link
                key={path}
                to={path}
                className={`flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium ${
                  active ? 'text-primary' : 'text-gray-500'
                }`}
              >
                <Icon className="h-5 w-5" strokeWidth={active ? 2.2 : 1.8} aria-hidden />
                {name}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
