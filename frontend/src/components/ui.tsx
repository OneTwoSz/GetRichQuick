import { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

// Small shared primitives so pages share one visual language.

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900 sm:text-[28px]">{title}</h1>
        {description && <p className="mt-1 text-sm text-gray-500">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({
  title,
  description,
  actions,
  children,
  className = '',
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl bg-white shadow ${className}`}>
      {(title || actions) && (
        <div className="flex items-start justify-between gap-3 px-5 pt-5">
          <div>
            {title && <h2 className="text-[15px] font-semibold text-gray-900">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-gray-500">{description}</p>}
          </div>
          {actions}
        </div>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

const TONES = {
  primary: 'bg-primary-50 text-primary-600',
  accent: 'bg-red-50 text-accent',
  amber: 'bg-amber-50 text-amber-600',
  blue: 'bg-blue-50 text-blue-600',
  gray: 'bg-gray-100 text-gray-600',
};

export function StatTile({
  label,
  value,
  unit,
  hint,
  Icon,
  tone = 'primary',
  alert = false,
}: {
  label: string;
  value: string;
  unit?: string;
  hint?: string;
  Icon: LucideIcon;
  tone?: keyof typeof TONES;
  alert?: boolean;
}) {
  return (
    <div className="min-w-0 rounded-xl bg-white p-4 shadow transition-shadow hover:shadow-md sm:p-5">
      <div className="flex items-center justify-between">
        <span className="truncate text-[13px] font-medium text-gray-500">{label}</span>
        <span className={`inline-flex h-8 w-8 items-center justify-center rounded-lg ${TONES[tone]}`}>
          <Icon className="h-4 w-4" strokeWidth={2} aria-hidden />
        </span>
      </div>
      <div className="mt-3 flex flex-wrap items-baseline gap-x-1.5 gap-y-1">
        <span
          className={`text-[26px] font-semibold leading-none tracking-tight tabular-nums ${
            alert ? 'text-red-600' : 'text-gray-900'
          }`}
        >
          {value}
        </span>
        {unit && <span className="whitespace-nowrap text-xs font-medium text-gray-500">{unit}</span>}
      </div>
      {hint && <div className="mt-2 text-xs text-gray-500">{hint}</div>}
    </div>
  );
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center py-16" role="status" aria-label={label}>
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  );
}
