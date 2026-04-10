'use client';

import { useEffect, useRef, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement, PointElement,
  ArcElement, Title, Tooltip, Legend,
} from 'chart.js';
import { Bar, Pie } from 'react-chartjs-2';
import ReportExportModal from '@/components/ReportExportModal';

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, ArcElement, Title, Tooltip, Legend);

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
const PERIODS = [
  { label: 'Last 24 Hours', days: 1 },
  { label: 'Last 7 Days', days: 7 },
  { label: 'Last 30 Days', days: 30 },
  { label: 'Last 90 Days', days: 90 },
];
const PAGE_SIZES = [10, 25, 50, 100];

interface DataPoint { name: string; value: number; unit: string; timestamp: string; }
interface Trend { parameter_id: number; name: string; unit: string; min: number; max: number; avg: number; count: number; last_seen: string | null; }
interface Alert { parameter_id: number; name: string; value: number; unit: string; timestamp: string; reason: string; }
interface Comparison { name: string; unit: string; min: number; max: number; avg: number; count: number; }
interface Meta { total_data_points: number; generated_at: string; start_date: string; end_date: string; }
type SortKey = 'name' | 'value' | 'timestamp';
type SortDir = 'asc' | 'desc';

const CHART_COLORS = ['#6366f1','#22d3ee','#f59e0b','#10b981','#f43f5e','#a78bfa','#34d399','#fb923c'];

export default function ReportsContent() {
  const router = useRouter();
  const [days, setDays] = useState(7);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [dataPoints, setDataPoints] = useState<DataPoint[]>([]);
  const [trends, setTrends] = useState<Trend[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [comparison, setComparison] = useState<Comparison[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  const [exportOpen, setExportOpen] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const alertsSetRef = useRef<Set<string>>(new Set());

  // Data points table state
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('timestamp');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const getRange = (d: number) => {
    const end = new Date();
    const start = new Date(end.getTime() - d * 86400000);
    return { start: start.toISOString(), end: end.toISOString() };
  };

  const loadReport = async (selectedDays = days) => {
    const token = localStorage.getItem('token');
    if (!token) { router.push('/login'); return; }
    setMeta(null); setDataPoints([]); setTrends([]); setAlerts([]); setComparison([]);
    setDone(false); setError(''); setStreaming(true); setPage(1);
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    alertsSetRef.current = new Set<string>(); // reset dedup set for this stream session
    const { start, end } = getRange(selectedDays);
    const sseUrl = `${BACKEND}/api/reports/full/stream?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}&limit=500&token=${encodeURIComponent(token)}`;
    try {
      const es = new EventSource(sseUrl);
      esRef.current = es;
      let gotAny = false;
      es.onmessage = (e) => {
        gotAny = true;
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'meta') setMeta({ total_data_points: msg.total_data_points, generated_at: msg.generated_at, start_date: msg.start_date, end_date: msg.end_date });
          else if (msg.type === 'data_point') setDataPoints(prev => {
            const p = msg.payload;
            // Deduplicate by name+timestamp
            const key = p.name + '|' + p.timestamp;
            if (prev.some(x => x.name + '|' + x.timestamp === key)) return prev;
            return [...prev, p];
          });
          else if (msg.type === 'trends') setTrends(msg.payload);
          else if (msg.type === 'alerts') {
            const incoming = (msg.payload as Alert[]).filter(a => {
              const k = a.parameter_id + '|' + a.timestamp;
              if (alertsSetRef.current.has(k)) return false;
              alertsSetRef.current.add(k);
              return true;
            });
            if (incoming.length > 0) setAlerts(prev => [...prev, ...incoming]);
          }
          else if (msg.type === 'comparison') setComparison(msg.payload);
          else if (msg.type === 'done') { setDone(true); setStreaming(false); es.close(); }
        } catch { /* ignore */ }
      };
      es.onerror = () => {
        es.close();
        esRef.current = null;
        // Only fallback if we got zero events (stream never started)
        if (!gotAny) fallbackFetch(token, start, end);
        else { setStreaming(false); setDone(true); }
      };
    } catch { fallbackFetch(token, start, end); }
  };

  const fallbackFetch = async (token: string, start: string, end: string) => {
    try {
      const res = await fetch(`/api/reports/full?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}&limit=500`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) { router.push('/login'); return; }
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      setMeta({ total_data_points: data.total_data_points, generated_at: data.generated_at, start_date: data.start_date, end_date: data.end_date });
      setDataPoints(data.data_points || []);
      setTrends(data.trends || []);
      setAlerts(data.alerts || []);
      setComparison(data.comparison || []);
      setDone(true);
    } catch (e: any) { setError(e.message || 'Failed to load report'); }
    finally { setStreaming(false); }
  };

  const downloadFile = async (format: 'csv' | 'pdf') => {
    const token = localStorage.getItem('token');
    if (!token) return;
    const { start, end } = getRange(days);
    try {
      const res = await fetch(`/api/reports/full/export/${format}?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}&limit=500`, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) { setError(`Export failed: ${res.status}`); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = `precisionpulse_report.${format}`; a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) { setError(e.message || 'Export failed'); }
  };

  useEffect(() => {
    if (!localStorage.getItem('token')) { router.push('/login'); return; }
    loadReport();
    return () => esRef.current?.close();
  }, []);

  const handlePeriod = (d: number) => { setDays(d); loadReport(d); };

  // --- Filtered / sorted / paginated data points ---
  const filtered = useMemo(() => {
    let rows = dataPoints;
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(r => r.name.toLowerCase().includes(q));
    }
    rows = [...rows].sort((a, b) => {
      let av: string | number = a[sortKey];
      let bv: string | number = b[sortKey];
      if (sortKey === 'timestamp') { av = new Date(av).getTime(); bv = new Date(bv).getTime(); }
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return rows;
  }, [dataPoints, search, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
    setPage(1);
  };

  const SortIcon = ({ k }: { k: SortKey }) =>
    sortKey === k ? <span className="ml-1 text-indigo-400">{sortDir === 'asc' ? '↑' : '↓'}</span> : <span className="ml-1 text-slate-600">↕</span>;

  // --- Trends chart data ---
  const trendsChartData = useMemo(() => ({
    labels: trends.map(t => t.name),
    datasets: [
      { label: 'Min', data: trends.map(t => t.min), backgroundColor: '#22d3ee', borderRadius: 4 },
      { label: 'Avg', data: trends.map(t => t.avg), backgroundColor: '#a78bfa', borderRadius: 4 },
      { label: 'Max', data: trends.map(t => t.max), backgroundColor: '#fbff0be0', borderRadius: 4 },
    ],
  }), [trends]);

  // --- Comparison pie chart data (avg per parameter) ---
  const compChartData = useMemo(() => ({
    labels: comparison.map(c => `${c.name} (${c.unit})`),
    datasets: [{
      data: comparison.map(c => c.avg),
      backgroundColor: CHART_COLORS.slice(0, comparison.length).map(c => c + 'cc'),
      borderColor: CHART_COLORS.slice(0, comparison.length),
      borderWidth: 1,
    }],
  }), [comparison]);

  const barChartOptions = {
    responsive: true,
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { size: 12 } } },
      title: { display: false },
      tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.dataset.label}: ${ctx.parsed.y}` } },
    },
    scales: {
      x: { ticks: { color: '#64748b' }, grid: { color: '#1e293b' } },
      y: { ticks: { color: '#64748b' }, grid: { color: '#1e293b' } },
    },
  };

  const pieChartOptions = {
    responsive: true,
    plugins: {
      legend: { position: 'right' as const, labels: { color: '#94a3b8', font: { size: 12 }, padding: 16 } },
      tooltip: { callbacks: { label: (ctx: any) => ` ${ctx.label}: ${ctx.parsed}` } },
    },
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 border-b border-indigo-500/20 sticky top-0 z-50">
        <div className="px-4 sm:px-8 py-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <div>
            <h1 className="text-lg sm:text-2xl font-bold text-white">Reports & Analytics</h1>
            <p className="text-xs sm:text-sm text-slate-400">Streamed parameter data · trends · alerts · comparison</p>
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <select value={days} onChange={(e) => handlePeriod(Number(e.target.value))} className="px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-white text-sm">
              {PERIODS.map(p => <option key={p.days} value={p.days}>{p.label}</option>)}
            </select>
            <button onClick={() => loadReport()} disabled={streaming} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg font-semibold text-sm">
              {streaming ? ' Loading…' : ' Refresh'}
            </button>
            <button onClick={() => downloadFile('csv')} disabled={!done} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 text-white rounded-lg font-semibold text-sm"> CSV</button>
            <button onClick={() => downloadFile('pdf')} disabled={!done} className="px-4 py-2 bg-rose-600 hover:bg-rose-700 disabled:opacity-40 text-white rounded-lg font-semibold text-sm"> PDF</button>
            <button onClick={() => setExportOpen(true)} className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg font-semibold text-sm"> Custom PDF</button>
          </div>
        </div>
      </div>

      <ReportExportModal
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        availableParams={trends.map(t => ({ id: t.parameter_id, name: t.name, unit: t.unit }))}
        mode="telemetry"
      />
      <div className="px-4 sm:px-8 lg:px-16 py-8 space-y-8">
        {error && <div className="bg-red-900/40 border border-red-500/40 rounded-xl p-4 text-red-300 text-sm">{error}</div>}

        {/* Summary cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Total Data Points', value: meta?.total_data_points?.toLocaleString() ?? (streaming ? '…' : '—'), color: 'text-white' },
            { label: 'Parameters', value: trends.length > 0 ? trends.length : (streaming ? '…' : '—'), color: 'text-indigo-400' },
            { label: 'Alerts', value: done ? alerts.length : (streaming ? '…' : '—'), color: alerts.length > 0 ? 'text-red-400' : 'text-emerald-400' },
            { label: 'Loaded Rows', value: dataPoints.length.toLocaleString(), color: 'text-sky-400' },
          ].map(c => (
            <div key={c.label} className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-5">
              <p className="text-slate-400 text-xs font-semibold mb-1">{c.label}</p>
              <p className={`text-3xl font-bold ${c.color}`}>{c.value}</p>
            </div>
          ))}
        </div>

        {meta && (
          <p className="text-slate-500 text-xs">
            Generated: {new Date(meta.generated_at).toLocaleString()} &nbsp;|&nbsp;
            Period: {new Date(meta.start_date).toLocaleDateString()} – {new Date(meta.end_date).toLocaleDateString()}
          </p>
        )}

        {/* ── Data Points ── */}
        <Section title="Streamed Data Points" subtitle={`Showing ${paginated.length} of ${filtered.length} rows${streaming ? ' (loading…)' : ''}`}>
          {/* Search + page size */}
          <div className="px-5 py-3 flex flex-col sm:flex-row gap-3 border-b border-slate-700/50">
            <input
              type="text"
              placeholder="Search by parameter name…"
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              className="flex-1 px-3 py-2 rounded-lg bg-slate-700/60 border border-slate-600 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <select value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }} className="px-3 py-2 rounded-lg bg-slate-700/60 border border-slate-600 text-white text-sm">
              {PAGE_SIZES.map(s => <option key={s} value={s}>{s} / page</option>)}
            </select>
          </div>

          {dataPoints.length === 0 && !streaming ? <Empty /> : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-700/50">
                    <tr>
                      <th className="px-5 py-3 text-left font-semibold text-slate-300 cursor-pointer select-none" onClick={() => toggleSort('name')}>Parameter Name <SortIcon k="name" /></th>
                      <th className="px-5 py-3 text-left font-semibold text-slate-300 cursor-pointer select-none" onClick={() => toggleSort('value')}>Value <SortIcon k="value" /></th>
                      <th className="px-5 py-3 text-left font-semibold text-slate-300">Unit</th>
                      <th className="px-5 py-3 text-left font-semibold text-slate-300 cursor-pointer select-none" onClick={() => toggleSort('timestamp')}>Timestamp <SortIcon k="timestamp" /></th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginated.map((dp, i) => (
                      <tr key={i} className="border-t border-slate-700/40 hover:bg-slate-700/20">
                        <td className="px-5 py-2 font-medium text-white">{dp.name}</td>
                        <td className="px-5 py-2 font-mono text-sky-300">{dp.value}</td>
                        <td className="px-5 py-2 text-slate-400">{dp.unit}</td>
                        <td className="px-5 py-2 text-slate-400 text-xs">{new Date(dp.timestamp).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Pagination */}
              <div className="px-5 py-3 flex flex-col sm:flex-row items-center justify-between gap-2 border-t border-slate-700/50">
                <span className="text-slate-500 text-xs">Page {page} of {totalPages} · {filtered.length} rows</span>
                <div className="flex gap-1">
                  <PagBtn label="«" onClick={() => setPage(1)} disabled={page === 1} />
                  <PagBtn label="‹" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} />
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    const start = Math.max(1, Math.min(page - 2, totalPages - 4));
                    const n = start + i;
                    return n <= totalPages ? (
                      <PagBtn key={n} label={String(n)} onClick={() => setPage(n)} active={page === n} />
                    ) : null;
                  })}
                  <PagBtn label="›" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} />
                  <PagBtn label="»" onClick={() => setPage(totalPages)} disabled={page === totalPages} />
                </div>
              </div>
            </>
          )}
        </Section>

        {/* ── Trends ── */}
        <Section title="Trends" subtitle="Min / Avg / Max per parameter — table + chart">
          {trends.length === 0 ? <Empty /> : (
            <>
              {/* Chart */}
              <div className="px-6 pt-6 pb-2">
                <Bar data={trendsChartData} options={barChartOptions} height={90} />
              </div>
              {/* Table */}
              <div className="overflow-x-auto mt-2">
                <table className="w-full text-sm">
                  <thead className="bg-slate-700/50">
                    <tr>
                      {['Parameter', 'Unit', 'Min', 'Max', 'Avg', 'Readings', 'Last Seen'].map(h => (
                        <th key={h} className="px-5 py-3 text-left font-semibold text-slate-300">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {trends.map(t => (
                      <tr key={t.parameter_id} className="border-t border-slate-700/40 hover:bg-slate-700/20">
                        <td className="px-5 py-2 font-medium text-white">{t.name}</td>
                        <td className="px-5 py-2 text-slate-400">{t.unit}</td>
                        <td className="px-5 py-2 font-mono text-blue-400">{t.min}</td>
                        <td className="px-5 py-2 font-mono text-red-400">{t.max}</td>
                        <td className="px-5 py-2 font-mono text-emerald-400">{t.avg}</td>
                        <td className="px-5 py-2 text-slate-400">{t.count.toLocaleString()}</td>
                        <td className="px-5 py-2 text-slate-500 text-xs">{t.last_seen ? new Date(t.last_seen).toLocaleString() : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Section>

        {/* ── Alerts ── */}
        <Section title={`Alerts (${done ? alerts.length : '…'})`} subtitle="Values outside thresholds or statistical outliers (±3σ)" accent="red">
          {!done ? (
            <p className="px-6 py-4 text-slate-400 text-sm">Loading…</p>
          ) : alerts.length === 0 ? (
            <p className="px-6 py-4 text-emerald-400 text-sm">✓ No alerts detected in this period.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-red-900/30">
                  <tr>
                    {['Parameter', 'Value', 'Unit', 'Timestamp', 'Reason'].map(h => (
                      <th key={h} className="px-5 py-3 text-left font-semibold text-red-300">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((a, i) => (
                    <tr key={i} className="border-t border-red-900/30 hover:bg-red-900/10">
                      <td className="px-5 py-2 font-medium text-white">{a.name}</td>
                      <td className="px-5 py-2 font-mono text-red-400">{a.value}</td>
                      <td className="px-5 py-2 text-slate-400">{a.unit}</td>
                      <td className="px-5 py-2 text-slate-400 text-xs">{new Date(a.timestamp).toLocaleString()}</td>
                      <td className="px-5 py-2 text-red-300 text-xs">{a.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        {/* ── Comparison ── */}
        <Section title="Parameter Comparison" subtitle="All parameters ranked by average value — chart + table">
          {comparison.length === 0 ? <Empty /> : (
            <>
              {/* Pie chart — avg value share per parameter */}
              <div className="px-6 pt-6 pb-2 flex justify-center">
                <div style={{ maxWidth: 480, width: '100%' }}>
                  <Pie data={compChartData} options={pieChartOptions} />
                </div>
              </div>
              {/* Table */}
              <div className="overflow-x-auto mt-2">
                <table className="w-full text-sm">
                  <thead className="bg-slate-700/50">
                    <tr>
                      {['Rank', 'Parameter', 'Unit', 'Min', 'Max', 'Avg', 'Readings'].map(h => (
                        <th key={h} className="px-5 py-3 text-left font-semibold text-slate-300">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.map((c, i) => (
                      <tr key={c.name} className="border-t border-slate-700/40 hover:bg-slate-700/20">
                        <td className="px-5 py-2 text-slate-500 font-mono">#{i + 1}</td>
                        <td className="px-5 py-2 font-medium text-white">{c.name}</td>
                        <td className="px-5 py-2 text-slate-400">{c.unit}</td>
                        <td className="px-5 py-2 font-mono text-blue-400">{c.min}</td>
                        <td className="px-5 py-2 font-mono text-red-400">{c.max}</td>
                        <td className="px-5 py-2 font-mono text-emerald-400 font-semibold">{c.avg}</td>
                        <td className="px-5 py-2 text-slate-400">{c.count.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Section>
      </div>
    </div>
  );
}

function Section({ title, subtitle, children, accent = 'indigo' }: {
  title: string; subtitle: string; children: React.ReactNode; accent?: string;
}) {
  const border = accent === 'red' ? 'border-red-500/30' : 'border-indigo-500/20';
  return (
    <div className={`bg-slate-800/50 border ${border} rounded-2xl overflow-hidden`}>
      <div className="px-6 py-4 border-b border-slate-700/50">
        <h3 className="text-base font-bold text-white">{title}</h3>
        <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

function Empty() {
  return <p className="px-6 py-6 text-slate-500 text-sm text-center">No data available for this period.</p>;
}

function PagBtn({ label, onClick, disabled, active }: { label: string; onClick: () => void; disabled?: boolean; active?: boolean; }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
        active ? 'bg-indigo-600 text-white' :
        disabled ? 'text-slate-600 cursor-not-allowed' :
        'text-slate-400 hover:bg-slate-700 hover:text-white'
      }`}
    >
      {label}
    </button>
  );
}
