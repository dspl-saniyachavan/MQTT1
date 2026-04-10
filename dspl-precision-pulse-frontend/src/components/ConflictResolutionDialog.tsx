'use client';

import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';

interface Conflict {
  id: string;
  resource_type: string;
  resource_id: string;
  local_version: any;
  remote_version: any;
  timestamp: string;
}

interface ConflictResolutionDialogProps {
  conflict: Conflict | null;
  onResolve: (conflictId: string, resolution: 'local' | 'remote') => void;
  onClose: () => void;
}

export function ConflictResolutionDialog({
  conflict,
  onResolve,
  onClose
}: ConflictResolutionDialogProps) {
  const { token } = useAuth();
  const [resolving, setResolving] = useState(false);

  if (!conflict) return null;

  const handleResolve = async (resolution: 'local' | 'remote') => {
    if (!token) return;

    try {
      setResolving(true);
      const response = await fetch(`/api/conflicts/${conflict.id}/resolve`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ resolution })
      });

      if (response.ok) {
        onResolve(conflict.id, resolution);
        onClose();
      }
    } catch (err) {
      console.error('Failed to resolve conflict:', err);
    } finally {
      setResolving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4">
        <div className="p-6 border-b">
          <h2 className="text-xl font-semibold">Resolve Conflict</h2>
          <p className="text-sm text-gray-600 mt-1">
            {conflict.resource_type} #{conflict.resource_id}
          </p>
        </div>

        <div className="p-6 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            {/* Local Version */}
            <div className="border rounded-lg p-4 bg-blue-50">
              <h3 className="font-semibold text-blue-900 mb-3">Local Version</h3>
              <pre className="text-xs bg-white p-3 rounded border border-blue-200 overflow-auto max-h-48">
                {JSON.stringify(conflict.local_version, null, 2)}
              </pre>
              <button
                onClick={() => handleResolve('local')}
                disabled={resolving}
                className="mt-3 w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                Keep Local
              </button>
            </div>

            {/* Remote Version */}
            <div className="border rounded-lg p-4 bg-green-50">
              <h3 className="font-semibold text-green-900 mb-3">Remote Version</h3>
              <pre className="text-xs bg-white p-3 rounded border border-green-200 overflow-auto max-h-48">
                {JSON.stringify(conflict.remote_version, null, 2)}
              </pre>
              <button
                onClick={() => handleResolve('remote')}
                disabled={resolving}
                className="mt-3 w-full px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
              >
                Keep Remote
              </button>
            </div>
          </div>

          <div className="text-xs text-gray-600">
            Conflict detected at {new Date(conflict.timestamp).toLocaleString()}
          </div>
        </div>

        <div className="p-6 border-t flex justify-end gap-2">
          <button
            onClick={onClose}
            disabled={resolving}
            className="px-4 py-2 text-gray-700 border rounded hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
