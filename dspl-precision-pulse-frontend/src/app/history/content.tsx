'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Line } from 'react-chartjs-2';
import PaginationControls from '@/components/PaginationControls';
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Title, Tooltip, Legend, Filler,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

interface HistoryRecord { timestamp: string; value: number; id: number; }
interface Parameter { id: number; name: string; unit: string; }

const COLORS = ['#4f46e5','#10b981','#f59e0b','#84cc16','#8b5cf6','#06b6d4','#ec4899','#ef4444'];
const API = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

const PRESETS: Record<string, string> = {
  last_15_minutes: 'Last 15 min', last_30_minutes: 'Last 30 min',
  last_hour: 'Last 1 hour', last_6_hours: 'Last 6 hours',
  last_24_hours: 'Last 24 hours', last_7_days: 'Last 7 days',
  last_30_days: 'Last 30 days', custom: 'Custom Range',
};

const PAGE_SIZES = [10, 25, 50, 100];

export default function HistoryContent() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [parameters, setParameters] = useState<Parameter[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [preset, setPreset] = useState('last_24_hours');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [dateRangeError, setDateRangeError] = useState('');
  const [recordsMap, setRecordsMap] = useState<Record<number, HistoryRecord[]>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [lastRefresh, setLastRefresh] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [searchTimestamp, setSearchTimestamp] = useState('');
  const [cursors, setCursors] = useState<string[]>(['']);

  useEffect(() => {
    if (!localStorage.getItem('token')) { router.push('/login'); return; }
    setIsAuthenticated(true);
  }, [router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const token = localStorage.getItem('token');
    fetch(`${API}/api/parameters`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        const params: Parameter[] = data?.parameters || [];
        setParameters(params);
        if (params.length > 0) setSelectedIds(new Set([params[0].id]));
      })
      .catch(() => setError('Failed to load parameters'));
  }, [isAuthenticated]);

  const fmtLocal = (d: Date) => {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  const fmtDisplay = (s: string) => {
    if (!s) return '';
    const d = new Date(s);
    return `${String(d.getDate()).padStart(2,'0')}-${d.toLocaleString('en-US',{month:'short'})}-${d.getFullYear()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;
  };

  const validateRange = (from: string, to: string) => {
    if (!from || !to) return 'Please select both dates';
    if (new Date(from) >= new Date(to)) return 'Start must be before end';
    const days = Math.ceil(Math.abs(new Date(to).getTime() - new Date(from).getTime()) / 86400000);
    if (days > 90) return `Range cannot exceed 90 days (${days} days selected)`;
    return '';
  };

  const loadHistory = useCallback(async (
    overridePreset?: string, overrideFrom?: string, overrideTo?: string
  ) => {
    if (selectedIds.size === 0) return;
    const activePreset = overridePreset ?? preset;
    const activeFrom   = overrideFrom   ?? fromDate;
    const activeTo     = overrideTo     ?? toDate;

    if (activePreset === 'custom') {
      const err = validateRange(activeFrom, activeTo);
      if (err) { setDateRangeError(err); return; }
    }

    setLoading(true); setError(''); setCurrentPage(1); setCursors(['']);
    const token = localStorage.getItem('token');

    const results = await Promise.all(
      [...selectedIds].map(async (id) => {
        let url = `${API}/api/telemetry/parameter/${id}/history-range?preset=${activePreset}&limit=2000`;
        if (activePreset === 'custom') url += `&start_date=${activeFrom}:00&end_date=${activeTo}:00`;
        try {
          const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` }, credentials: 'include' });
          if (!res.ok) return { id, records: [] };
          const data = await res.json();
          const sorted = (data.records || []).slice().sort(
            (a: HistoryRecord, b: HistoryRecord) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
          );
          return { id, records: sorted };
        } catch { return { id, records: [] }; }
      })
    );

    const map: Record<number, HistoryRecord[]> = {};
    results.forEach(({ id, records }) => { map[id] = records; });
    setRecordsMap(map);
    setLastRefresh(new Date().toLocaleTimeString());
    setDateRangeError('');
    setLoading(false);
  }, [selectedIds, preset, fromDate, toDate]);

  useEffect(() => {
    if (isAuthenticated && selectedIds.size > 0 && preset !== 'custom') loadHistory();
  }, [selectedIds, preset, isAuthenticated]);

  const toggleParam = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) { if (next.size > 1) next.delete(id); }
      else next.add(id);
      return next;
    });
  };

  const allTimestamps = [...new Set(
    Object.values(recordsMap).flatMap(recs => recs.map(r => r.timestamp))
  )].sort((a, b) => new Date(b).getTime() - new Date(a).getTime());

  const valueLookup: Record<number, Record<string, number>> = {};
  selectedIds.forEach(id => {
    valueLookup[id] = {};
    (recordsMap[id] || []).forEach(r => { valueLookup[id][r.timestamp] = r.value; });
  });

  const filteredTimestamps = searchTimestamp
    ? allTimestamps.filter(ts => fmtDisplay(ts).toLowerCase().includes(searchTimestamp.toLowerCase()))
    : allTimestamps;

  const totalPages = Math.ceil(filteredTimestamps.length / itemsPerPage);
  const pageStart = (currentPage - 1) * itemsPerPage;
  const paginatedTimestamps = filteredTimestamps.slice(pageStart, pageStart + itemsPerPage);
  const selectedParamList = parameters.filter(p => selectedIds.has(p.id));
  const chartTimestamps = [...filteredTimestamps].reverse();

  const chartData = {
    labels: chartTimestamps.map(ts => fmtDisplay(ts)),
    datasets: selectedParamList.map((param, i) => ({
      label: `${param.name} (${param.unit})`,
      data: chartTimestamps.map(ts => valueLookup[param.id]?.[ts] ?? null),
      borderColor: COLORS[i % COLORS.length],
      backgroundColor: COLORS[i % COLORS.length] + '22',
      borderWidth: 2,
      fill: false,
      tension: 0.3,
      pointRadius: 3,
      pointHoverRadius: 7,
      pointBackgroundColor: COLORS[i % COLORS.length],
      pointBorderColor: COLORS[i % COLORS.length],
      spanGaps: true,
    })),
  };

  const chartOptions: any = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index' as const, intersect: false },
    plugins: {
      legend: { display: true, labels: { color: '#cbd5e1', font: { size: 12 }, usePointStyle: true, pointStyle: 'circle' } },
      tooltip: {
        enabled: true,
        mode: 'index' as const,
        intersect: false,
        backgroundColor: 'rgba(15,23,42,0.97)',
        titleColor: '#94a3b8',
        bodyColor: '#cbd5e1',
        borderColor: '#334155',
        borderWidth: 1,
        padding: 12,
        callbacks: {
          label: (ctx: any) => ` ${ctx.dataset.label}: ${ctx.parsed.y !== null ? Number(ctx.parsed.y).toFixed(2) : '—'}`,
        },
      },
    },
    scales: {
      x: { grid: { color: 'rgba(148,163,184,0.08)' }, ticks: { color: '#64748b', font: { size: 10 }, maxRotation: 45, maxTicksLimit: 8 } },
      y: { grid: { color: 'rgba(148,163,184,0.12)' }, ticks: { color: '#94a3b8', font: { size: 11 } } },
    },
  };

  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 border-b border-indigo-500/20 sticky top-0 z-50">
        <div className="px-4 sm:px-8 lg:px-20 py-4">
          <h1 className="text-lg sm:text-2xl font-bold text-white">Parameter History</h1>
          <p className="text-xs sm:text-sm text-slate-400">Historical telemetry — available even when desktop is offline</p>
        </div>
      </div>

      <div className="px-4 sm:px-8 lg:px-20 py-8 space-y-6">
        {/* Controls */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 space-y-5">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-3 uppercase tracking-widest">Parameters</label>
            <div className="flex flex-wrap gap-2">
              {parameters.map((p, i) => (
                <label key={p.id} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-pointer text-xs font-semibold transition-all
                  ${selectedIds.has(p.id) ? 'border-transparent text-white' : 'border-slate-600 text-slate-400 bg-slate-700/40 hover:border-slate-500'}`}
                  style={selectedIds.has(p.id) ? { backgroundColor: COLORS[i % COLORS.length] + '33', borderColor: COLORS[i % COLORS.length] } : {}}
                >
                  <input type="checkbox" checked={selectedIds.has(p.id)} onChange={() => toggleParam(p.id)} className="accent-indigo-500" />
                  <span style={selectedIds.has(p.id) ? { color: COLORS[i % COLORS.length] } : {}}>{p.name}</span>
                  <span className="text-slate-500">({p.unit})</span>
                </label>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[180px]">
              <label className="block text-xs font-semibold text-slate-300 mb-1 uppercase tracking-widest">Time Range</label>
              <select value={preset} onChange={e => {
                const v = e.target.value; setPreset(v); setDateRangeError(''); setCurrentPage(1);
                if (v === 'custom') {
                  const now = new Date();
                  setFromDate(fmtLocal(new Date(now.getTime() - 90*86400000)));
                  setToDate(fmtLocal(now));
                } else { loadHistory(v); }
              }} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-indigo-500 focus:outline-none">
                {Object.entries(PRESETS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <button onClick={() => loadHistory()} disabled={loading}
              className="px-5 py-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold transition-all">
              {loading ? '⟳ Loading…' : '⟳ Refresh'}
            </button>
            {lastRefresh && <span className="text-xs text-slate-500">Last: {lastRefresh}</span>}
          </div>

          {preset === 'custom' && (
            <div className="p-4 bg-slate-700/30 border border-slate-600 rounded-lg space-y-3">
              <p className="text-xs text-slate-400 font-semibold">Maximum range: 90 days</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-slate-300 mb-1 font-semibold">From</label>
                  <input type="datetime-local" value={fromDate}
                    onChange={e => { setFromDate(e.target.value); setDateRangeError(validateRange(e.target.value, toDate)); }}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-indigo-500 focus:outline-none" />
                </div>
                <div>
                  <label className="block text-xs text-slate-300 mb-1 font-semibold">To</label>
                  <input type="datetime-local" value={toDate}
                    onChange={e => { setToDate(e.target.value); setDateRangeError(validateRange(fromDate, e.target.value)); }}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-indigo-500 focus:outline-none" />
                </div>
              </div>
              {dateRangeError && <p className="text-red-400 text-xs font-semibold">{dateRangeError}</p>}
              <button onClick={() => loadHistory('custom', fromDate, toDate)}
                disabled={loading || !!dateRangeError || !fromDate || !toDate}
                className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold">
                {loading ? 'Loading…' : 'Search'}
              </button>
            </div>
          )}

          <div className="flex items-center gap-3">
            <div className="flex-1">
              <label className="block text-xs font-semibold text-slate-300 mb-1 uppercase tracking-widest">Search by Timestamp</label>
              <input type="text" placeholder="e.g. 07-Jan-2026 or 07:07" value={searchTimestamp}
                onChange={e => { setSearchTimestamp(e.target.value); setCurrentPage(1); }}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-xs focus:border-indigo-500 focus:outline-none" />
            </div>
            {searchTimestamp && (
              <button onClick={() => { setSearchTimestamp(''); setCurrentPage(1); }}
                className="mt-5 text-xs text-red-400 hover:text-red-300 font-semibold">Clear</button>
            )}
          </div>
        </div>

        {error && <div className="bg-red-600/20 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm font-semibold">{error}</div>}

        {/* Chart */}
        {chartTimestamps.length > 0 && (
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-white">Trend — {selectedParamList.map(p => p.name).join(', ')}</h2>
              <span className="text-xs text-slate-500">{PRESETS[preset]}</span>
            </div>
            <div style={{ height: 360 }}>
              <Line data={chartData} options={chartOptions} />
            </div>
          </div>
        )}

        {/* Table */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between flex-wrap gap-3">
            <div>
              <h2 className="text-base font-semibold text-white">History Table</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                {filteredTimestamps.length} rows • {PRESETS[preset]}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Rows per page:</span>
              <select value={itemsPerPage} onChange={e => { setItemsPerPage(Number(e.target.value)); setCurrentPage(1); }}
                className="px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-xs focus:outline-none">
                {PAGE_SIZES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {loading ? (
            <div className="p-10 text-center text-slate-400 text-sm">Loading data…</div>
          ) : filteredTimestamps.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-slate-700/50 border-b border-slate-600">
                    <tr>
                      <th className="px-4 py-3 text-left text-slate-300 font-semibold whitespace-nowrap">Timestamp</th>
                      {selectedParamList.map((p, i) => (
                        <th key={p.id} className="px-4 py-3 text-right font-semibold whitespace-nowrap"
                          style={{ color: COLORS[i % COLORS.length] }}>
                          {p.name} ({p.unit})
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedTimestamps.map(ts => (
                      <tr key={ts} className="border-b border-slate-700/60 hover:bg-slate-700/20 transition-colors">
                        <td className="px-4 py-2.5 text-slate-300 whitespace-nowrap">{fmtDisplay(ts)}</td>
                        {selectedParamList.map((p, i) => {
                          const val = valueLookup[p.id]?.[ts];
                          return (
                            <td key={p.id} className="px-4 py-2.5 text-right font-semibold"
                              style={{ color: val !== undefined ? COLORS[i % COLORS.length] : '#475569' }}>
                              {val !== undefined ? val.toFixed(2) : '—'}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <PaginationControls
                currentPage={currentPage}
                totalPages={totalPages}
                itemsPerPage={itemsPerPage}
                totalRecords={filteredTimestamps.length}
                onPageChange={p => setCurrentPage(p)}
              />
            </>
          ) : (
            <div className="p-10 text-center text-slate-400 text-sm">
              {Object.keys(recordsMap).length === 0
                ? 'No data loaded yet. Select parameters and a time range.'
                : 'No records match your search.'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
