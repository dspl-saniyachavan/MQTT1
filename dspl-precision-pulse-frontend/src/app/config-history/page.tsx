'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

interface HistoryEntry {
  id: number;
  key: string;
  version_number: number;
  config_data: Record<string, any>;
  changed_by: string;
  change_description: string;
  created_at: string;
}

const API = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

export default function ConfigHistoryPage() {
  const router = useRouter();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterKey, setFilterKey] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');
    if (!token) { router.push('/login'); return; }
    const parsed = user ? JSON.parse(user) : {};
    if (parsed.role !== 'admin') { router.push('/dashboard'); return; }
    loadHistory();
  }, [router]);

  const loadHistory = async (key?: string) => {
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const params = new URLSearchParams({ limit: '100' });
      if (key) params.set('key', key);
      const res = await fetch(`${API}/api/config/history?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setHistory(data.history || []);
      } else {
        setError(`Failed to load history: ${res.status}`);
      }
    } catch (e: any) {
      setError(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleFilter = () => loadHistory(filterKey || undefined);
  const uniqueKeys = [...new Set(history.map(h => h.key))];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 border-b border-indigo-500/20 sticky top-0 z-50">
        <div className="px-4 sm:px-8 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg sm:text-2xl font-bold text-white">Config Version History</h1>
            <p className="text-xs sm:text-sm text-slate-400">View configuration change history</p>
          </div>
          <button onClick={() => router.push('/config')} className="text-slate-400 hover:text-white text-sm">
            ← Configuration
          </button>
        </div>
      </div>

      <div className="px-4 sm:px-8 lg:px-20 py-8">
        {/* Filter */}
        <div className="flex gap-3 mb-6">
          <select
            value={filterKey}
            onChange={e => setFilterKey(e.target.value)}
            className="flex-1 max-w-xs px-4 py-2 bg-slate-800 border border-slate-700 text-white rounded-lg focus:border-indigo-500 focus:outline-none text-sm"
          >
            <option value="">All Keys</option>
            {uniqueKeys.map(k => <option key={k} value={k}>{k}</option>)}
          </select>
          <button onClick={handleFilter}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold">
            Filter
          </button>
          <button onClick={() => { setFilterKey(''); loadHistory(); }}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm">
            Clear
          </button>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-900/30 border border-red-500/30 rounded-lg text-red-400 text-sm">{error}</div>
        )}

        {loading ? (
          <div className="text-center py-12 text-slate-400">Loading history...</div>
        ) : history.length === 0 ? (
          <div className="text-center py-12 bg-slate-800/50 border border-slate-700 rounded-lg">
            <p className="text-slate-400">No version history found</p>
          </div>
        ) : (
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-700/50 border-b border-slate-600">
                <tr>
                  <th className="px-6 py-3 text-left text-slate-300 font-semibold">Key</th>
                  <th className="px-6 py-3 text-left text-slate-300 font-semibold">Version</th>
                  <th className="px-6 py-3 text-left text-slate-300 font-semibold">Value</th>
                  <th className="px-6 py-3 text-left text-slate-300 font-semibold">Changed By</th>
                  <th className="px-6 py-3 text-left text-slate-300 font-semibold">Description</th>
                  <th className="px-6 py-3 text-left text-slate-300 font-semibold">Date</th>
                </tr>
              </thead>
              <tbody>
                {history.map(entry => (
                  <tr key={entry.id} className="border-b border-slate-700 hover:bg-slate-700/30 transition-colors">
                    <td className="px-6 py-3 text-white font-mono text-xs">{entry.key}</td>
                    <td className="px-6 py-3">
                      <span className="px-2 py-1 bg-yellow-900/30 text-yellow-400 rounded text-xs font-semibold">
                        v{entry.version_number}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-emerald-400 font-mono text-xs max-w-xs truncate">
                      {JSON.stringify(entry.config_data?.value ?? entry.config_data)}
                    </td>
                    <td className="px-6 py-3 text-slate-400 text-xs">{entry.changed_by || 'system'}</td>
                    <td className="px-6 py-3 text-slate-400 text-xs max-w-xs truncate">
                      {entry.change_description || '—'}
                    </td>
                    <td className="px-6 py-3 text-slate-500 text-xs whitespace-nowrap">
                      {new Date(entry.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
