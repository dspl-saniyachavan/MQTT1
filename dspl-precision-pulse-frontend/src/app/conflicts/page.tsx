'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Pagination from '@/components/Pagination';

interface Conflict {
  id: number;
  resource_type: string;
  resource_id: string;
  backend_version: Record<string, any>;
  desktop_version: Record<string, any>;
  resolved: boolean;
  resolution_method: string | null;
  resolved_at: string | null;
  created_at: string;
}

const API = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

export default function ConflictsPage() {
  const router = useRouter();
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [resolving, setResolving] = useState<number | null>(null);
  const [filter, setFilter] = useState<'all' | 'unresolved' | 'resolved'>('unresolved');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');
    if (!token) { router.push('/login'); return; }
    const parsed = user ? JSON.parse(user) : {};
    if (parsed.role !== 'admin') { router.push('/dashboard'); return; }
    loadConflicts();
  }, [router]);

  const loadConflicts = async () => {
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API}/api/conflicts?limit=100`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setConflicts(data.conflicts || []);
      } else {
        setError(`Failed to load conflicts: ${res.status}`);
      }
    } catch (e: any) {
      setError(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const resolve = async (id: number, resolution: 'local' | 'remote') => {
    setResolving(id);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API}/api/conflicts/${id}/resolve`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolution }),
      });
      if (res.ok) {
        setConflicts(prev =>
          prev.map(c => c.id === id ? { ...c, resolved: true, resolution_method: resolution, resolved_at: new Date().toISOString() } : c)
        );
      } else {
        const data = await res.json();
        setError(data.message || 'Failed to resolve conflict');
      }
    } catch (e: any) {
      setError(`Error: ${e.message}`);
    } finally {
      setResolving(null);
    }
  };

  const filtered = conflicts.filter(c => {
    if (filter === 'unresolved') return !c.resolved;
    if (filter === 'resolved') return c.resolved;
    return true;
  });

  const unresolvedCount = conflicts.filter(c => !c.resolved).length;
  const totalPages = Math.ceil(filtered.length / pageSize);
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 border-b border-indigo-500/20 sticky top-0 z-50">
        <div className="px-4 sm:px-8 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg sm:text-2xl font-bold text-white">Conflict Resolution</h1>
            <p className="text-xs sm:text-sm text-slate-400">Resolve sync conflicts between backend and desktop</p>
          </div>
          <button onClick={() => router.push('/dashboard')} className="text-slate-400 hover:text-white text-sm">
            ← Dashboard
          </button>
        </div>
      </div>

      <div className="px-4 sm:px-8 lg:px-20 py-8">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-red-600/20 border border-red-500/30 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-red-400">{unresolvedCount}</div>
            <div className="text-xs text-slate-400 mt-1">Unresolved</div>
          </div>
          <div className="bg-green-600/20 border border-green-500/30 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-green-400">{conflicts.length - unresolvedCount}</div>
            <div className="text-xs text-slate-400 mt-1">Resolved</div>
          </div>
          <div className="bg-blue-600/20 border border-blue-500/30 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-blue-400">{conflicts.length}</div>
            <div className="text-xs text-slate-400 mt-1">Total</div>
          </div>
        </div>

        {/* Filter */}
        <div className="flex gap-2 mb-6">
          {(['all', 'unresolved', 'resolved'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg text-sm font-semibold capitalize transition ${
                filter === f ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
              }`}>
              {f}
            </button>
          ))}
          <button onClick={loadConflicts} className="ml-auto px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm">
            Refresh
          </button>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-900/30 border border-red-500/30 rounded-lg text-red-400 text-sm">{error}</div>
        )}

        {loading ? (
          <div className="text-center py-12 text-slate-400">Loading conflicts...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 bg-slate-800/50 border border-slate-700 rounded-lg">
            <p className="text-slate-400">No {filter === 'all' ? '' : filter} conflicts found</p>
          </div>
        ) : (
          <div className="space-y-4">
            {paginated.map(conflict => (
              <div key={conflict.id}
                className={`bg-slate-800/50 border rounded-xl p-6 ${
                  conflict.resolved ? 'border-green-500/20' : 'border-red-500/30'
                }`}>
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <span className="text-white font-semibold capitalize">{conflict.resource_type}</span>
                    <span className="text-slate-400 text-sm ml-2">ID: {conflict.resource_id}</span>
                    <span className={`ml-3 px-2 py-0.5 rounded text-xs font-semibold ${
                      conflict.resolved
                        ? 'bg-green-600/20 text-green-400'
                        : 'bg-red-600/20 text-red-400'
                    }`}>
                      {conflict.resolved ? `Resolved (${conflict.resolution_method})` : 'Unresolved'}
                    </span>
                  </div>
                  <span className="text-slate-500 text-xs">{new Date(conflict.created_at).toLocaleString()}</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div className="bg-slate-900 rounded-lg p-4">
                    <div className="text-xs font-semibold text-blue-400 mb-2 uppercase tracking-wider">Backend Version</div>
                    <pre className="text-xs text-slate-300 overflow-auto max-h-32 whitespace-pre-wrap">
                      {JSON.stringify(conflict.backend_version, null, 2)}
                    </pre>
                  </div>
                  <div className="bg-slate-900 rounded-lg p-4">
                    <div className="text-xs font-semibold text-amber-400 mb-2 uppercase tracking-wider">Desktop Version</div>
                    <pre className="text-xs text-slate-300 overflow-auto max-h-32 whitespace-pre-wrap">
                      {JSON.stringify(conflict.desktop_version, null, 2)}
                    </pre>
                  </div>
                </div>

                {!conflict.resolved && (
                  <div className="flex gap-3">
                    <button
                      onClick={() => resolve(conflict.id, 'remote')}
                      disabled={resolving === conflict.id}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold"
                    >
                      {resolving === conflict.id ? 'Resolving...' : 'Use Backend Version'}
                    </button>
                    <button
                      onClick={() => resolve(conflict.id, 'local')}
                      disabled={resolving === conflict.id}
                      className="px-4 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold"
                    >
                      Use Desktop Version
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
