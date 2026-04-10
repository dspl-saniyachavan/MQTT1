'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import ProtectedPage from '@/components/ProtectedPage';

interface Permission {
  id: number;
  role: string;
  resource: string;
  action: string;
  allowed: boolean;
}

export default function PermissionsPage() {
  const { token } = useAuth();
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRole, setSelectedRole] = useState<string>('');
  const [newPerm, setNewPerm] = useState({ resource: '', action: '', allowed: true });

  useEffect(() => {
    fetchPermissions();
  }, [token]);

  const fetchPermissions = async () => {
    if (!token) return;

    try {
      setLoading(true);
      const response = await fetch('/api/permissions', {
        headers: { Authorization: `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setPermissions(data.permissions || []);
        const uniqueRoles = [...new Set(data.permissions?.map((p: Permission) => p.role) || [])] as string[];
        setRoles(uniqueRoles);
        if (uniqueRoles.length > 0) {
          setSelectedRole(uniqueRoles[0]);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch permissions');
    } finally {
      setLoading(false);
    }
  };

  const handleAddPermission = async () => {
    if (!token || !selectedRole || !newPerm.resource || !newPerm.action) return;

    try {
      const response = await fetch('/api/permissions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          role: selectedRole,
          resource: newPerm.resource,
          action: newPerm.action,
          allowed: newPerm.allowed
        })
      });

      if (response.ok) {
        setNewPerm({ resource: '', action: '', allowed: true });
        await fetchPermissions();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add permission');
    }
  };

  const handleDeletePermission = async (permId: number) => {
    if (!token) return;

    try {
      const perm = permissions.find(p => p.id === permId);
      if (!perm) return;

      const response = await fetch(
        `/api/permissions/${perm.role}/${perm.resource}/${perm.action}`,
        {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      if (response.ok) {
        await fetchPermissions();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete permission');
    }
  };

  const filteredPermissions = permissions.filter(p => p.role === selectedRole);

  return (
    <ProtectedPage requiredPermission="manage_users">
      <div className="max-w-6xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-6">Permission Management</h1>

        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <p>Loading...</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Role Selector */}
            <div className="lg:col-span-1">
              <div className="bg-white rounded-lg shadow p-4">
                <h2 className="font-semibold mb-4">Roles</h2>
                <div className="space-y-2">
                  {roles.map(role => (
                    <button
                      key={role}
                      onClick={() => setSelectedRole(role)}
                      className={`w-full text-left px-4 py-2 rounded ${
                        selectedRole === role
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 hover:bg-gray-200'
                      }`}
                    >
                      {role}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Permissions List and Add Form */}
            <div className="lg:col-span-2 space-y-6">
              {/* Add Permission Form */}
              <div className="bg-white rounded-lg shadow p-4">
                <h2 className="font-semibold mb-4">Add Permission</h2>
                <div className="space-y-3">
                  <input
                    type="text"
                    placeholder="Resource (e.g., users, config)"
                    value={newPerm.resource}
                    onChange={(e) => setNewPerm({ ...newPerm, resource: e.target.value })}
                    className="w-full px-3 py-2 border rounded"
                  />
                  <input
                    type="text"
                    placeholder="Action (e.g., read, write)"
                    value={newPerm.action}
                    onChange={(e) => setNewPerm({ ...newPerm, action: e.target.value })}
                    className="w-full px-3 py-2 border rounded"
                  />
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={newPerm.allowed}
                      onChange={(e) => setNewPerm({ ...newPerm, allowed: e.target.checked })}
                    />
                    <span>Allowed</span>
                  </label>
                  <button
                    onClick={handleAddPermission}
                    className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Add Permission
                  </button>
                </div>
              </div>

              {/* Permissions Table */}
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="px-4 py-3 text-left text-sm font-semibold">Resource</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold">Action</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold">Allowed</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPermissions.map(perm => (
                      <tr key={perm.id} className="border-b hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm">{perm.resource}</td>
                        <td className="px-4 py-3 text-sm">{perm.action}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            perm.allowed
                              ? 'bg-green-100 text-green-800'
                              : 'bg-red-100 text-red-800'
                          }`}>
                            {perm.allowed ? 'Yes' : 'No'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <button
                            onClick={() => handleDeletePermission(perm.id)}
                            className="text-red-600 hover:text-red-800"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </ProtectedPage>
  );
}
