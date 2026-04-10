'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';

interface BufferStatus {
  user_changes_buffered: number;
  config_changes_buffered: number;
  total_buffered: number;
}

export function BufferStatusIndicator() {
  const { token } = useAuth();
  const [bufferStatus, setBufferStatus] = useState<BufferStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBufferStatus = async () => {
    if (!token) return;
    
    try {
      setLoading(true);
      const response = await fetch('/api/sync/buffer/status', {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        setBufferStatus(data);
        setError(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch buffer status');
    } finally {
      setLoading(false);
    }
  };
  const handleFlush = async () => {
    if (!token) return;
    
    try {
      const response = await fetch('/api/sync/buffer/flush', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.ok) {
        await fetchBufferStatus();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to flush buffer');
    }
  };

  useEffect(() => {
    fetchBufferStatus();
    const interval = setInterval(fetchBufferStatus, 5000);
    return () => clearInterval(interval);
  }, [token]);

  if (!bufferStatus) return null;

  if (bufferStatus.total_buffered === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 bg-yellow-50 border border-yellow-200 rounded-lg p-4 shadow-lg">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-yellow-900">Pending Changes</p>
          <p className="text-xs text-yellow-700 mt-1">
            Users: {bufferStatus.user_changes_buffered} | Config: {bufferStatus.config_changes_buffered}
          </p>
        </div>
        <button
          onClick={handleFlush}
          disabled={loading}
          className="px-3 py-1 bg-yellow-600 text-white text-sm rounded hover:bg-yellow-700 disabled:opacity-50"
        >
          {loading ? 'Flushing...' : 'Flush'}
        </button>
      </div>
      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
    </div>
  );
}
