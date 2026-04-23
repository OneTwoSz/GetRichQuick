import { useState, useEffect, FormEvent } from 'react';
import { reportsAPI } from '@/services/api';
import type { Report, ReportFormData, ReportType } from '@/types';

export default function Reports() {
  const [reports, setReports] = useState<Report[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [formData, setFormData] = useState<ReportFormData>({
    date_from: '',
    date_to: '',
    report_type: 'monthly',
  });

  useEffect(() => {
    loadReports();
  }, []);

  const loadReports = async () => {
    try {
      const data = await reportsAPI.getAll();
      setReports(data);
    } catch (err) {
      console.error('Failed to load reports', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setGenerating(true);
    try {
      await reportsAPI.generate(formData);
      setShowForm(false);
      setFormData({
        date_from: '',
        date_to: '',
        report_type: 'monthly',
      });
      loadReports();
    } catch (err) {
      console.error('Failed to generate report', err);
      alert('Failed to generate report. Make sure you have production data for the selected period.');
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async (id: number) => {
    try {
      await reportsAPI.download(id);
    } catch (err) {
      console.error('Failed to download report', err);
      alert('Failed to download report');
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  if (loading) {
    return <div className="text-center py-12">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Sustainability Reports</h1>
          <p className="mt-1 text-sm text-gray-600">
            Generate and download professional sustainability reports
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-600"
        >
          {showForm ? 'Cancel' : '+ Generate Report'}
        </button>
      </div>

      {/* Report Generation Form */}
      {showForm && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">Generate New Report</h2>
          </div>
          <form onSubmit={handleSubmit} className="p-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700">Report Type</label>
                <select
                  name="report_type"
                  value={formData.report_type}
                  onChange={handleChange}
                  required
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="custom">Custom Period</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">From Date</label>
                <input
                  type="date"
                  name="date_from"
                  value={formData.date_from}
                  onChange={handleChange}
                  required
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">To Date</label>
                <input
                  type="date"
                  name="date_to"
                  value={formData.date_to}
                  onChange={handleChange}
                  required
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={generating}
              className="w-full py-2 px-4 bg-primary text-white rounded-lg hover:bg-primary-600 disabled:opacity-50"
            >
              {generating ? 'Generating Report...' : 'Generate Report'}
            </button>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-medium text-blue-900 mb-2">What's included in the report:</h4>
              <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
                <li>Carbon footprint summary and breakdown</li>
                <li>Water and energy usage metrics</li>
                <li>Chemical compliance status</li>
                <li>Audit trail reference for data traceability</li>
                <li>Professional PDF ready to send to EU buyers</li>
              </ul>
            </div>
          </form>
        </div>
      )}

      {/* Reports List */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Generated Reports</h2>
        </div>
        <div className="overflow-x-auto">
          {reports.length === 0 ? (
            <div className="p-6 text-center text-gray-500">
              No reports generated yet. Click "Generate Report" to create your first sustainability
              report.
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Report Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Period
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Total Carbon (kg CO₂e)
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Carbon/Garment
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Generated
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {reports.map((report) => (
                  <tr key={report.id}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {report.report_type.charAt(0).toUpperCase() + report.report_type.slice(1)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(report.date_from).toLocaleDateString()} -{' '}
                      {new Date(report.date_to).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {report.total_carbon_kg.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {report.carbon_per_garment_kg.toFixed(3)} kg
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(report.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <button
                        onClick={() => handleDownload(report.id)}
                        className="text-primary hover:text-primary-600 font-medium"
                      >
                        Download PDF
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-primary-50 border border-primary-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-primary-900 mb-2">
          Why GreenThread Reports Matter
        </h3>
        <p className="text-primary-800 mb-4">
          EU regulations (CSRD for brands, Digital Product Passport from 2027) require textile
          manufacturers to provide auditable sustainability data. Our reports give you:
        </p>
        <ul className="text-primary-800 space-y-2 list-disc list-inside">
          <li>Professional, buyer-ready documentation</li>
          <li>Full traceability through audit logs</li>
          <li>Compliance with EU reporting requirements</li>
          <li>Competitive advantage when working with H&M, Zara, M&S, and other EU brands</li>
        </ul>
      </div>
    </div>
  );
}
