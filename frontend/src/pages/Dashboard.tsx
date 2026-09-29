import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { dashboardAPI, factoryAPI } from '@/services/api';
import type { DashboardSummary } from '@/types';
import {
  AlertTriangle,
  ArrowRight,
  ClipboardList,
  Droplets,
  FileText,
  Factory,
  Info,
  RefreshCcw,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { Card, PageHeader, Spinner, StatTile } from '@/components/ui';
import DemoTour from '@/components/DemoTour';

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true';

export default function Dashboard() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      // Check if factory exists
      try {
        await factoryAPI.get();
      } catch (err) {
        // Factory not found, redirect to setup
        navigate('/factory-setup');
        return;
      }

      const data = await dashboardAPI.getSummary();
      setSummary(data);
    } catch (err) {
      setError('Failed to load dashboard');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <Spinner label="Loading dashboard" />;
  }

  if (error) {
    return <div className="py-12 text-center text-red-600">{error}</div>;
  }

  if (!summary) {
    return null;
  }

  const SEVERITY = {
    high: { style: 'border-red-200 bg-red-50 text-red-800', Icon: AlertTriangle },
    medium: { style: 'border-amber-200 bg-amber-50 text-amber-800', Icon: Zap },
    low: { style: 'border-blue-200 bg-blue-50 text-blue-800', Icon: Info },
  } as const;

  const rework = (summary.rework_rate ?? 0) * 100;
  const actions = [
    { label: 'Log production data', hint: 'Batches, inputs and bills', path: '/production', Icon: ClipboardList },
    { label: 'Generate report', hint: 'Signed and verifiable', path: '/reports', Icon: FileText },
    { label: 'Manage chemicals', hint: 'REACH and ZDHC status', path: '/compliance', Icon: ShieldCheck },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="This month's sustainability performance at a glance" />

      {DEMO_MODE && <DemoTour />}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-5">
        <StatTile
          label="Carbon"
          value={summary.carbon_footprint_this_month.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          unit="kg CO₂e"
          hint="This month"
          Icon={Factory}
        />
        <StatTile
          label="Water"
          value={(summary.water_usage_this_month / 1000).toFixed(1)}
          unit="kL"
          hint="This month"
          Icon={Droplets}
          tone="blue"
        />
        <StatTile
          label="Compliance"
          value={`${summary.chemical_compliance_percentage.toFixed(0)}%`}
          hint="Chemicals REACH and ZDHC"
          Icon={ShieldCheck}
          tone={summary.chemical_compliance_percentage < 100 ? 'amber' : 'primary'}
        />
        <StatTile
          label="Reports"
          value={String(summary.reports_generated)}
          hint="Signed sustainability reports"
          Icon={FileText}
          tone="gray"
        />
        <StatTile
          label="Rework"
          value={`${rework.toFixed(1)}%`}
          hint="Rework batches ÷ total"
          Icon={RefreshCcw}
          tone={rework > 10 ? 'accent' : 'primary'}
          alert={rework > 10}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card
          title="Alerts and actions"
          description={summary.alerts.length ? `${summary.alerts.length} item(s) need attention` : 'Nothing needs attention'}
          className="lg:col-span-2"
        >
          {summary.alerts.length === 0 ? (
            <p className="text-sm text-gray-500">All clear — no compliance or data issues this month.</p>
          ) : (
            <ul className="space-y-2.5">
              {summary.alerts.map((alert, index) => {
                const sev = SEVERITY[alert.severity as keyof typeof SEVERITY] ?? SEVERITY.low;
                return (
                  <li key={index} className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${sev.style}`}>
                    <sev.Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                    <span className="font-medium">{alert.message}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card title="Quick actions">
          <div className="space-y-2">
            {actions.map(({ label, hint, path, Icon }) => (
              <button
                key={path}
                onClick={() => navigate(path)}
                className="group flex w-full items-center gap-3 rounded-lg border border-gray-200 px-3 py-3 text-left transition-colors hover:border-primary/40 hover:bg-primary-50"
              >
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100 text-gray-600 group-hover:bg-primary group-hover:text-white">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <span className="flex-1">
                  <span className="block text-sm font-medium text-gray-900">{label}</span>
                  <span className="block text-xs text-gray-500">{hint}</span>
                </span>
                <ArrowRight className="h-4 w-4 text-gray-300 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
              </button>
            ))}
          </div>
        </Card>
      </div>

      {summary.carbon_footprint_this_month === 0 && (
        <div className="rounded-xl border border-primary-200 bg-primary-50 p-6">
          <h3 className="text-base font-semibold text-primary-900">Get started</h3>
          <p className="mt-1 text-sm text-primary-800">
            No production data logged for this month yet. Log your first batch to see your sustainability
            metrics.
          </p>
          <button
            onClick={() => navigate('/production')}
            className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-600"
          >
            Log your first batch
          </button>
        </div>
      )}
    </div>
  );
}
