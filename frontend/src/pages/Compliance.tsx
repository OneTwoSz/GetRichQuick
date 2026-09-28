import { useState, useEffect, FormEvent } from 'react';
import { chemicalsAPI } from '@/services/api';
import type { Chemical, ChemicalFormData } from '@/types';

export default function Compliance() {
  const [chemicals, setChemicals] = useState<Chemical[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState<ChemicalFormData>({
    chemical_name: '',
    supplier: '',
    quantity_kg: 0,
    cas_number: '',
    reach_compliant: false,
    zdhc_compliant: false,
    certificate_url: '',
    expiry_date: '',
  });

  useEffect(() => {
    loadChemicals();
  }, []);

  const loadChemicals = async () => {
    try {
      const data = await chemicalsAPI.getAll();
      setChemicals(data);
    } catch (err) {
      console.error('Failed to load chemicals', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        await chemicalsAPI.update(editingId, formData);
      } else {
        await chemicalsAPI.create(formData);
      }
      resetForm();
      loadChemicals();
    } catch (err) {
      console.error('Failed to save chemical', err);
      alert('Failed to save chemical data');
    }
  };

  const handleEdit = (chemical: Chemical) => {
    setFormData({
      chemical_name: chemical.chemical_name,
      supplier: chemical.supplier || '',
      quantity_kg: chemical.quantity_kg,
      cas_number: chemical.cas_number || '',
      reach_compliant: chemical.reach_compliant,
      zdhc_compliant: chemical.zdhc_compliant,
      certificate_url: chemical.certificate_url || '',
      expiry_date: chemical.expiry_date
        ? new Date(chemical.expiry_date).toISOString().split('T')[0]
        : '',
    });
    setEditingId(chemical.id);
    setShowForm(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this chemical?')) return;
    try {
      await chemicalsAPI.delete(id);
      loadChemicals();
    } catch (err) {
      console.error('Failed to delete chemical', err);
      alert('Failed to delete chemical');
    }
  };

  const resetForm = () => {
    setFormData({
      chemical_name: '',
      supplier: '',
      quantity_kg: 0,
      cas_number: '',
      reach_compliant: false,
      zdhc_compliant: false,
      certificate_url: '',
      expiry_date: '',
    });
    setEditingId(null);
    setShowForm(false);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : type === 'number' ? parseFloat(value) || 0 : value,
    }));
  };

  const compliancePercentage =
    chemicals.length > 0
      ? (chemicals.filter((c) => c.reach_compliant && c.zdhc_compliant).length /
          chemicals.length) *
        100
      : 0;

  if (loading) {
    return <div className="text-center py-12">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-gray-900 sm:text-[28px]">Chemical Compliance</h1>
          <p className="mt-1 text-sm text-gray-600">Manage and track chemical compliance</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-600"
        >
          {showForm ? 'Cancel' : '+ Add Chemical'}
        </button>
      </div>

      {/* Compliance Overview */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Compliance Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="text-sm text-gray-600">Total Chemicals</div>
            <div className="text-3xl font-bold text-gray-900">{chemicals.length}</div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Compliant</div>
            <div className="text-3xl font-bold text-green-600">
              {chemicals.filter((c) => c.reach_compliant && c.zdhc_compliant).length}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Compliance Rate</div>
            <div className="text-3xl font-bold text-primary">{compliancePercentage.toFixed(0)}%</div>
          </div>
        </div>
      </div>

      {/* Chemical Form */}
      {showForm && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">
              {editingId ? 'Edit Chemical' : 'Add Chemical'}
            </h2>
          </div>
          <form onSubmit={handleSubmit} className="p-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700">Chemical Name</label>
                <input
                  type="text"
                  name="chemical_name"
                  value={formData.chemical_name}
                  onChange={handleChange}
                  required
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Supplier</label>
                <input
                  type="text"
                  name="supplier"
                  value={formData.supplier}
                  onChange={handleChange}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Quantity (kg)</label>
                <input
                  type="number"
                  name="quantity_kg"
                  value={formData.quantity_kg}
                  onChange={handleChange}
                  required
                  min="0"
                  step="0.01"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">CAS Number</label>
                <input
                  type="text"
                  name="cas_number"
                  value={formData.cas_number}
                  onChange={handleChange}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="e.g., 7732-18-5"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Certificate URL
                </label>
                <input
                  type="url"
                  name="certificate_url"
                  value={formData.certificate_url}
                  onChange={handleChange}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Expiry Date</label>
                <input
                  type="date"
                  name="expiry_date"
                  value={formData.expiry_date}
                  onChange={handleChange}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    name="reach_compliant"
                    checked={formData.reach_compliant}
                    onChange={handleChange}
                    className="rounded text-primary focus:ring-primary"
                  />
                  <span className="text-sm font-medium text-gray-700">REACH Compliant</span>
                </label>
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    name="zdhc_compliant"
                    checked={formData.zdhc_compliant}
                    onChange={handleChange}
                    className="rounded text-primary focus:ring-primary"
                  />
                  <span className="text-sm font-medium text-gray-700">ZDHC Compliant</span>
                </label>
              </div>
            </div>

            <div className="flex gap-4">
              <button
                type="submit"
                className="flex-1 py-2 px-4 bg-primary text-white rounded-lg hover:bg-primary-600"
              >
                {editingId ? 'Update Chemical' : 'Add Chemical'}
              </button>
              {editingId && (
                <button
                  type="button"
                  onClick={resetForm}
                  className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Cancel Edit
                </button>
              )}
            </div>
          </form>
        </div>
      )}

      {/* Chemicals List */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Chemical Inventory</h2>
        </div>
        <div className="overflow-x-auto">
          {chemicals.length === 0 ? (
            <div className="p-6 text-center text-gray-500">
              No chemicals added yet. Click "Add Chemical" to start tracking compliance.
            </div>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Chemical Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Supplier
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Quantity (kg)
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    CAS Number
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Compliance
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {chemicals.map((chemical) => (
                  <tr key={chemical.id}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {chemical.chemical_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {chemical.supplier || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {chemical.quantity_kg.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {chemical.cas_number || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {chemical.reach_compliant && chemical.zdhc_compliant ? (
                        <span className="px-2 py-1 bg-green-100 text-green-800 rounded">
                          ✓ Compliant
                        </span>
                      ) : (
                        <span className="px-2 py-1 bg-red-100 text-red-800 rounded">
                          ✗ Non-compliant
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                      <button
                        onClick={() => handleEdit(chemical)}
                        className="text-primary hover:text-primary-600"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(chemical.id)}
                        className="text-red-600 hover:text-red-700"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
