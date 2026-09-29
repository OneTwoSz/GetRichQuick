import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Compass, X } from 'lucide-react';

// Guided tour for the hosted demo (VITE_DEMO_MODE=true). Links point at the
// stable demo tokens created by backend/app/jobs/seed_demo.py.

const STORAGE_KEY = 'gt-demo-tour-hidden';

const STEPS: { title: string; body: string; to: string; external?: boolean }[] = [
  {
    title: 'One dye lot, many orders',
    body: 'LOT-2026-0701-WHT fed two buyers’ orders. See how water, power and dye are split fairly — including a re-dye and leftover fabric.',
    to: '/batches',
  },
  {
    title: 'An order’s footprint',
    body: 'Orders → PO-2026-102 shows its allocation statement and how much is measured vs estimated.',
    to: '/orders',
  },
  {
    title: 'What the buyer sees',
    body: 'The read-only link a factory sends a brand instead of filling in spreadsheets.',
    to: '/share/demo-share-po-102',
    external: true,
  },
  {
    title: 'Fibre-to-landfill footprint',
    body: 'Products → Oversized Tee → Life cycle: every stage, its data source, and a “what if” comparison.',
    to: '/products',
  },
  {
    title: 'The product passport',
    body: 'What a shopper sees after scanning the care-label QR. Signed — tampering shows up.',
    to: '/passport/demo-oversized-tee',
    external: true,
  },
  {
    title: 'Print care-label QR codes',
    body: 'A print-ready sheet sized for wash-care labels.',
    to: '/passport/demo-oversized-tee/label',
    external: true,
  },
  {
    title: 'The dyer’s view',
    body: 'The polo was dyed outside — 0% primary data. Submit figures on this no-login form, then check the polo’s Life cycle tab again.',
    to: '/jobwork/demo-jobwork-token',
    external: true,
  },
  {
    title: 'The spinner’s view',
    body: 'Upstream suppliers share their numbers the same way — from a WhatsApp link.',
    to: '/supplier-data/demo-supplier-token',
    external: true,
  },
];

export default function DemoTour() {
  const [hidden, setHidden] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === '1';
    } catch {
      return false;
    }
  });

  const hide = () => {
    setHidden(true);
    try {
      localStorage.setItem(STORAGE_KEY, '1');
    } catch {
      // ignore
    }
  };

  if (hidden) {
    return (
      <button
        onClick={() => {
          setHidden(false);
          try {
            localStorage.removeItem(STORAGE_KEY);
          } catch {
            // ignore
          }
        }}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-primary"
      >
        <Compass className="h-3.5 w-3.5" aria-hidden /> Show the demo tour
      </button>
    );
  }

  return (
    <section className="rounded-xl border border-primary-200 bg-primary-50 p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-white">
            <Compass className="h-4 w-4" aria-hidden />
          </span>
          <div>
            <h2 className="text-[15px] font-semibold text-primary-900">Welcome to the demo factory</h2>
            <p className="mt-0.5 text-sm text-primary-800">
              Saravana Knits, Tiruppur — sample data that resets periodically. Try these in order:
            </p>
          </div>
        </div>
        <button onClick={hide} aria-label="Hide tour" className="rounded-md p-1 text-primary-700 hover:bg-primary-100">
          <X className="h-4 w-4" />
        </button>
      </div>
      <ol className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {STEPS.map((step, i) => {
          const inner = (
            <>
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-semibold text-primary-600">STEP {i + 1}</span>
                {step.external && <ArrowUpRight className="h-3.5 w-3.5 text-gray-400" aria-hidden />}
              </div>
              <div className="mt-1 text-sm font-medium text-gray-900">{step.title}</div>
              <div className="mt-1 text-xs leading-relaxed text-gray-500">{step.body}</div>
            </>
          );
          const cls = 'block h-full rounded-lg bg-white p-3 shadow-sm transition-shadow hover:shadow-md';
          return (
            <li key={step.to}>
              {step.external ? (
                <a href={step.to} target="_blank" rel="noreferrer" className={cls}>{inner}</a>
              ) : (
                <Link to={step.to} className={cls}>{inner}</Link>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
