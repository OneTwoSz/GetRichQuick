import { ReactNode } from 'react';
import { BadgeCheck, Layers, QrCode } from 'lucide-react';
import Logo from '@/components/Logo';
import { ThemeIconButton } from '@/components/ThemeToggle';

// Split-screen frame for sign-in / registration: the form on the left, a
// brand panel explaining the product on the right (large screens only).
export default function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  const points = [
    { Icon: Layers, title: 'Batch-level primary data', body: 'Log each dye lot once — footprints split fairly across every order it served.' },
    { Icon: BadgeCheck, title: 'Signed and tamper-evident', body: 'Every report and passport is cryptographically signed. Buyers can verify it.' },
    { Icon: QrCode, title: 'Product passports', body: 'Fibre-to-end-of-life footprints behind a QR code on the hangtag.' },
  ];

  return (
    <div className="grid min-h-screen bg-gray-50 lg:grid-cols-2">
      <div className="flex flex-col px-6 py-6 sm:px-10">
        <div className="flex items-center justify-between">
          <Logo />
          <ThemeIconButton />
        </div>
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-sm">
            <h1 className="text-2xl font-semibold tracking-tight text-gray-900">{title}</h1>
            <p className="mt-1.5 text-sm text-gray-500">{subtitle}</p>
            <div className="mt-8">{children}</div>
          </div>
        </div>
        <p className="text-xs text-gray-400">Sustainability data for textile manufacturers · Made for Tiruppur</p>
      </div>

      <div className="relative hidden overflow-hidden bg-[#06201d] lg:block">
        <div
          className="absolute inset-0 opacity-[0.18]"
          style={{
            backgroundImage: 'radial-gradient(rgb(94 229 208) 1px, transparent 1px)',
            backgroundSize: '22px 22px',
          }}
          aria-hidden
        />
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-[#34d3be] opacity-20 blur-3xl" aria-hidden />
        <div className="relative flex h-full flex-col justify-center px-14 xl:px-20">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#5ee5d0]">GreenThread</p>
          <h2 className="mt-4 max-w-md text-4xl font-semibold leading-tight tracking-tight text-[#ffffff]">
            Prove how every garment was made.
          </h2>
          <div className="mt-10 max-w-md space-y-6">
            {points.map(({ Icon, title, body }) => (
              <div key={title} className="flex gap-4">
                <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#ffffff1a] text-[#5ee5d0] ring-1 ring-[#ffffff1a]">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <div>
                  <div className="text-sm font-medium text-[#ffffff]">{title}</div>
                  <div className="mt-0.5 text-sm leading-relaxed text-[#ffffff99]">{body}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// Shared field + button styling for the auth forms.
export const authLabel = 'block text-sm font-medium text-gray-700';
export const authButton =
  'flex w-full justify-center rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-600 focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50';
