import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { factoryAPI } from '@/services/api';

export default function FactorySetup() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    name: '',
    location: '',
    gst_number: '',
    employee_count: '',
    production_capacity_kg_per_month: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = {
        name: formData.name,
        location: formData.location,
        gst_number: formData.gst_number || undefined,
        employee_count: formData.employee_count ? parseInt(formData.employee_count) : undefined,
        production_capacity_kg_per_month: formData.production_capacity_kg_per_month
          ? parseInt(formData.production_capacity_kg_per_month)
          : undefined,
      };

      await factoryAPI.create(data);
      navigate('/');
    } catch (err) {
      setError('Failed to create factory profile');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <h1 className="text-2xl font-bold text-gray-900">Factory Setup</h1>
          <p className="mt-1 text-sm text-gray-600">
            Set up your factory profile to start tracking sustainability metrics
          </p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

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
              placeholder="e.g., Tiruppur Textiles Pvt Ltd"
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
              placeholder="e.g., Tiruppur, Tamil Nadu"
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
              placeholder="e.g., 33XXXXX1234X1X5"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label htmlFor="employee_count" className="block text-sm font-medium text-gray-700">
                Number of Employees
              </label>
              <input
                type="number"
                id="employee_count"
                name="employee_count"
                min="1"
                value={formData.employee_count}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary"
                placeholder="e.g., 100"
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
                value={formData.production_capacity_kg_per_month}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary"
                placeholder="e.g., 50000"
              />
            </div>
          </div>

          <div className="pt-4">
            <button
              type="submit"
              disabled={loading}
              className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary hover:bg-primary-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create Factory Profile'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
