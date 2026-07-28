import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { dashboardAPI, factoryAPI } from '@/services/api';
import type { DashboardSummary } from '@/types';

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
    return <div className="text-center py-12">Loading dashboard...</div>;
  }

  if (error) {
    return <div className="text-red-600 text-center py-12">{error}</div>;
  }

  if (!summary) {
    return null;
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high':
        return 'bg-red-50 border-red-200 text-red-800';
      case 'medium':
        return 'bg-yellow-50 border-yellow-200 text-yellow-800';
      case 'low':
        return 'bg-blue-50 border-blue-200 text-blue-800';
      default:
        return 'bg-gray-50 border-gray-200 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-600">Overview of your sustainability metrics</p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-600">Carbon Footprint</div>
          <div className="mt-2 text-3xl font-bold text-primary">
            {summary.carbon_footprint_this_month.toFixed(2)}
          </div>
          <div className="text-sm text-gray-500">kg CO₂e this month</div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-600">Water Usage</div>
          <div className="mt-2 text-3xl font-bold text-primary">
            {(summary.water_usage_this_month / 1000).toFixed(1)}
          </div>
          <div className="text-sm text-gray-500">thousand liters this month</div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-600">Chemical Compliance</div>
          <div className="mt-2 text-3xl font-bold text-primary">
            {summary.chemical_compliance_percentage.toFixed(0)}%
          </div>
          <div className="text-sm text-gray-500">REACH & ZDHC compliant</div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-600">Reports Generated</div>
          <div className="mt-2 text-3xl font-bold text-primary">{summary.reports_generated}</div>
          <div className="text-sm text-gray-500">sustainability reports</div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm font-medium text-gray-600">Rework Rate</div>
          <div
            className={`mt-2 text-3xl font-bold ${
              (summary.rework_rate ?? 0) > 0.1 ? 'text-red-600' : 'text-primary'
            }`}
          >
            {((summary.rework_rate ?? 0) * 100).toFixed(1)}%
          </div>
          <div className="text-sm text-gray-500">rework batches ÷ total</div>
        </div>
      </div>

      {/* Alerts */}
      {summary.alerts.length > 0 && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Alerts & Actions</h2>
            <div className="space-y-3">
              {summary.alerts.map((alert, index) => (
                <div
                  key={index}
                  className={`border rounded-lg p-4 ${getSeverityColor(alert.severity)}`}
                >
                  <div className="flex items-start">
                    <span className="text-lg mr-3">
                      {alert.severity === 'high' ? '⚠️' : alert.severity === 'medium' ? '⚡' : 'ℹ️'}
                    </span>
                    <div>
                      <div className="font-medium">{alert.message}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button
              onClick={() => navigate('/production')}
              className="flex items-center justify-center px-4 py-3 bg-primary text-white rounded-lg hover:bg-primary-600 transition-colors"
            >
              <span className="mr-2">📝</span>
              Log Production Data
            </button>
            <button
              onClick={() => navigate('/reports')}
              className="flex items-center justify-center px-4 py-3 bg-primary text-white rounded-lg hover:bg-primary-600 transition-colors"
            >
              <span className="mr-2">📄</span>
              Generate Report
            </button>
            <button
              onClick={() => navigate('/compliance')}
              className="flex items-center justify-center px-4 py-3 bg-primary text-white rounded-lg hover:bg-primary-600 transition-colors"
            >
              <span className="mr-2">✓</span>
              Manage Chemicals
            </button>
          </div>
        </div>
      </div>

      {/* Empty State Guidance */}
      {summary.carbon_footprint_this_month === 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-blue-900 mb-2">Get Started</h3>
          <p className="text-blue-800 mb-4">
            No production data logged for this month yet. Start by logging your first production
            batch to see your sustainability metrics.
          </p>
          <button
            onClick={() => navigate('/production')}
            className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-600"
          >
            Log Your First Batch
          </button>
        </div>
      )}
    </div>
  );
}
