import { useState, useEffect, FormEvent } from 'react';
import { factoryAPI } from '@/services/api';
import type { Factory, FactoryFormData } from '@/types';

export default function Settings() {
  const [factory, setFactory] = useState<Factory | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [formData, setFormData] = useState<FactoryFormData>({
    name: '',
    location: '',
    gst_number: '',
    employee_count: undefined,
    production_capacity_kg_per_month: undefined,
  });

  useEffect(() => {
    loadFactory();
  }, []);

  const loadFactory = async () => {
    try {
      const data = await factoryAPI.get();
      setFactory(data);
      setFormData({
        name: data.name,
        location: data.location,
        gst_number: data.gst_number || '',
        employee_count: data.employee_count,
        production_capacity_kg_per_month: data.production_capacity_kg_per_month,
      });
    } catch (err) {
      console.error('Failed to load factory', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage('');
    try {
      await factoryAPI.update(formData);
      setMessage('Factory settings updated successfully');
      loadFactory();
    } catch (err) {
      console.error('Failed to update factory', err);
      setMessage('Failed to update settings');
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: ['employee_count', 'production_capacity_kg_per_month'].includes(name)
        ? value
          ? parseInt(value)
          : undefined
        : value,
    }));
  };

  if (loading) {
    return <div className="text-center py-12">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-600">Manage your factory profile and account settings</p>
      </div>

      {/* Factory Settings */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Factory Profile</h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {message && (
            <div
              className={`px-4 py-3 rounded ${
                message.includes('success')
                  ? 'bg-green-50 border border-green-200 text-green-700'
                  : 'bg-red-50 border border-red-200 text-red-700'
              }`}
            >
              {message}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                Factory Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="name"
                name="name"
                required
                value={formData.name}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary"
              />
            </div>

            <div>
              <label htmlFor="location" className="block text-sm font-medium text-gray-700">
                Location <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="location"
                name="location"
                required
                value={formData.location}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary"
              />
            </div>

            <div>
              <label htmlFor="gst_number" className="block text-sm font-medium text-gray-700">
                GST Number
              </label>
              <input
                type="text"
                id="gst_number"
                name="gst_number"
                value={formData.gst_number}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary"
              />
            </div>

            <div>
              <label htmlFor="employee_count" className="block text-sm font-medium text-gray-700">
                Number of Employees
              </label>
              <input
                type="number"
                id="employee_count"
                name="employee_count"
                min="1"
                value={formData.employee_count || ''}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary"
              />
            </div>

            <div>
              <label
                htmlFor="production_capacity_kg_per_month"
                className="block text-sm font-medium text-gray-700"
              >
                Monthly Capacity (kg)
              </label>
              <input
                type="number"
                id="production_capacity_kg_per_month"
                name="production_capacity_kg_per_month"
                min="1"
                value={formData.production_capacity_kg_per_month || ''}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={saving}
            className="w-full py-2 px-4 bg-primary text-white rounded-lg hover:bg-primary-600 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </form>
      </div>

      {/* Account Info */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Account Information</h2>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <div className="text-sm text-gray-600">Factory ID</div>
            <div className="text-base font-medium text-gray-900">{factory?.id}</div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Account Created</div>
            <div className="text-base font-medium text-gray-900">
              {factory?.created_at ? new Date(factory.created_at).toLocaleDateString() : '-'}
            </div>
          </div>
        </div>
      </div>

      {/* Support */}
      <div className="bg-primary-50 border border-primary-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-primary-900 mb-2">Need Help?</h3>
        <p className="text-primary-800 mb-4">
          For support with GreenThread or questions about sustainability reporting requirements,
          contact us:
        </p>
        <div className="space-y-2 text-primary-800">
          <div>Email: support@greenthread.io</div>
          <div>Website: www.greenthread.io</div>
        </div>
      </div>
    </div>
  );
}
