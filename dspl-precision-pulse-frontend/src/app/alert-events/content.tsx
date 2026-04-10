'use client';

import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { socketIOService } from '@/services/socketIOService';
import ReportExportModal, { type AvailableParam } from '@/components/ReportExportModal';

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
const HOURS_OPTIONS = [1, 6, 12, 24, 48, 168];

interface AlertEvent {
  id: number;
  parameter_id: number;
  parameter_name: string;
  value_at_trigger: number;
  peak_value: number;
  alert_min: number | null;
  alert_max: number | null;
  severity: 'warning' | 'critical';
  triggered_at: string;
  resolved_at: string | null;
  duration_seconds: number | null;
  duration_label: string;
  active: boolean;
}

interface ReportRow {
  parameter_id: number;
  parameter_name: string;
  alert_min: number | null;
  alert_max: number | null;
  total_events: number;
  active_events: number;
  critical_events: number;
  warning_events: number;
  max_value_reached: number | null;
  min_value_reached: number | null;
  avg_duration_s: number | null;
  max_duration_s: number | null;
  total_duration_s: number | null;
  events: AlertEvent[];
}

function fmtDur(s: number | null) {
  if (s === null) return 'Ongoing';
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}
const fmtTime = (iso: string) => new Date(iso).toLocaleString();

// ── Push notification helpers ─────────────────────────────────────────────────
async function registerPush(token: string): Promise<boolean> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return false;
  try {
    const keyRes = await fetch(`${BACKEND}/api/push/vapid-public-key`);
    const { publicKey } = await keyRes.json();
    if (!publicKey) return false;

    const reg = await navigator.serviceWorker.ready;
    const existing = await reg.pushManager.getSubscription();
    const sub = existing || await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
    await fetch(`${BACKEND}/api/push/subscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ subscription: sub.toJSON() }),
    });
    return true;
  } catch { return false; }
}

function urlBase64ToUint8Array(base64String: string) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(base64);
  return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
}

// ── Mini inline bar chart ─────────────────────────────────────────────────────
function MiniBarChart({ events, alertMin, alertMax }: {
  events: AlertEvent[]; alertMin: number | null; alertMax: number | null;
}) {
  if (events.length === 0) return null;
  const vals = events.map(e => e.peak_value ?? e.value_at_trigger);
  const lo = Math.min(...vals) * 0.95;
  const hi = Math.max(...vals) * 1.05 || 1;
  const range = hi - lo || 1;
  return (
    <div className="flex items-end gap-0.5 h-10 mt-2">
      {events.slice(-30).map((e, i) => {
        const h = Math.max(4, ((( e.peak_value ?? e.value_at_trigger) - lo) / range) * 40);
        const color = e.severity === 'critical' ? '#ef4444' : '#f59e0b';
        return (
          <div key={i} title={`${e.peak_value?.toFixed(2)} @ ${fmtTime(e.triggered_at)}`}
            style={{ height: h, backgroundColor: color, flex: 1, minWidth: 3, borderRadius: 2, opacity: e.active ? 1 : 0.6 }} />
        );
      })}
    </div>
  );
}

export default function AlertEventsContent() {
  const router = useRouter();
  const [tab, setTab] = useState<'events' | 'report'>('events');
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [report, setReport] = useState<ReportRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [hours, setHours] = useState(24);
  const [filter, setFilter] = useState<'all' | 'active' | 'resolved'>('all');
  const [severityFilter, setSeverityFilter] = useState<'all' | 'warning' | 'critical'>('all');
  const [expandedParam, setExpandedParam] = useState<number | null>(null);
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [sortField, setSortField] = useState<'triggered_at' | 'severity' | 'parameter_name' | 'duration_seconds'>('triggered_at');
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');
  const [eventsPage, setEventsPage] = useState(1);
  const EVENTS_PAGE_SIZE = 20;

  const token = useRef('');

  const availableParams: AvailableParam[] = useMemo(() => {
    const map = new Map<number, AvailableParam>();
    for (const ev of events) map.set(ev.parameter_id, { id: ev.parameter_id, name: ev.parameter_name, unit: '' });
    for (const row of report) map.set(row.parameter_id, { id: row.parameter_id, name: row.parameter_name, unit: '' });
    return Array.from(map.values());
  }, [events, report]);

  const fetchEvents = useCallback(async (h = hours, f = filter, sv = severityFilter) => {
    const t = localStorage.getItem('token');
    if (!t) { router.push('/login'); return; }
    token.current = t;
    setLoading(true);
    try {
      const activeQ = f === 'active' ? '&active=true' : f === 'resolved' ? '&active=false' : '';
      const sevQ = sv !== 'all' ? `&severity=${sv}` : '';
      const res = await fetch(`${BACKEND}/api/alert-events?hours=${h}${activeQ}${sevQ}`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (res.ok) {
        // Replace entire array with DB data — this drops any live Socket.IO
        // placeholder events that the DB now has as real rows.
        setEvents((await res.json()).events || []);
      }
    } finally { setLoading(false); }
  }, [hours, filter, severityFilter, router]);

  const fetchReport = useCallback(async (h = hours) => {
    const t = localStorage.getItem('token');
    if (!t) return;
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND}/api/alert-events/report?hours=${h}`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (res.ok) setReport((await res.json()).report || []);
    } finally { setLoading(false); }
  }, [hours]);

  useEffect(() => {
    if (tab === 'events') fetchEvents();
    else fetchReport();
  }, [tab, fetchEvents, fetchReport]);

  // Check push status on mount
  useEffect(() => {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      navigator.serviceWorker.ready.then(reg =>
        reg.pushManager.getSubscription().then(sub => setPushEnabled(!!sub))
      );
    }
  }, []);

  // Live SocketIO updates
  useEffect(() => {
    socketIOService.connectIfNeeded();
    // Use a negative counter for live events so they never collide with real DB ids
    let liveIdCounter = -1;
    const onTriggered = (data: any) => {
      const triggered_at = data.triggered_at || new Date().toISOString();
      setEvents(prev => {
        // Drop any existing live placeholder for this parameter (handles warning→critical
        // transition where two socket events fire in quick succession for the same param).
        const withoutOldLive = prev.filter(e =>
          !(e.id < 0 && e.parameter_id === data.parameter_id)
        );
        // Dedup: skip if a real DB row already exists for this parameter+triggered_at (±5s)
        const alreadyInDB = withoutOldLive.some(e =>
          e.id > 0 &&
          e.parameter_id === data.parameter_id &&
          Math.abs(new Date(e.triggered_at).getTime() - new Date(triggered_at).getTime()) < 5000
        );
        if (alreadyInDB) return withoutOldLive;
        const e: AlertEvent = {
          id: liveIdCounter--, parameter_id: data.parameter_id,
          parameter_name: data.parameter_name, value_at_trigger: data.current_value,
          peak_value: data.current_value, alert_min: data.alert_min ?? null,
          alert_max: data.alert_max ?? null, severity: data.severity || 'warning',
          triggered_at,
          resolved_at: null, duration_seconds: null, duration_label: 'Ongoing', active: true,
        };
        return [e, ...withoutOldLive];
      });
    };
    const onResolved = (data: AlertEvent) => {
      setEvents(prev => {
        // Remove any live placeholder for this parameter, then update the real DB row
        const withoutLive = prev.filter(e => !(e.id < 0 && e.parameter_id === data.parameter_id));
        return withoutLive.map(e =>
          e.parameter_id === data.parameter_id && e.active ? { ...data } : e
        );
      });
    };
    socketIOService.on('alert_triggered', onTriggered);
    socketIOService.on('alert_resolved', onResolved);
    const interval = setInterval(() => {
      if (tab === 'events') fetchEvents();
      else fetchReport();
    }, 30000);
    return () => {
      socketIOService.off('alert_triggered', onTriggered);
      socketIOService.off('alert_resolved', onResolved);
      clearInterval(interval);
    };
  }, [tab, fetchEvents, fetchReport]);

  const togglePush = async () => {
    setPushLoading(true);
    try {
      if (pushEnabled) {
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.getSubscription();
        if (sub) {
          await fetch(`${BACKEND}/api/push/unsubscribe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token.current}` },
            body: JSON.stringify({ subscription: sub.toJSON() }),
          });
          await sub.unsubscribe();
        }
        setPushEnabled(false);
      } else {
        const ok = await registerPush(token.current);
        setPushEnabled(ok);
      }
    } finally { setPushLoading(false); }
  };

  const activeCount    = events.filter(e => e.active).length;
  const criticalCount  = events.filter(e => e.severity === 'critical').length;
  const resolvedCount  = events.filter(e => !e.active).length;

  const sortedEvents = [...events].sort((a, b) => {
    let av: any = a[sortField], bv: any = b[sortField];
    if (sortField === 'triggered_at') { av = new Date(av).getTime(); bv = new Date(bv).getTime(); }
    if (sortField === 'severity') { av = av === 'critical' ? 1 : 0; bv = bv === 'critical' ? 1 : 0; }
    if (av === null || av === undefined) av = -Infinity;
    if (bv === null || bv === undefined) bv = -Infinity;
    return sortDir === 'desc' ? (bv > av ? 1 : -1) : (av > bv ? 1 : -1);
  });
  const totalEventPages = Math.max(1, Math.ceil(sortedEvents.length / EVENTS_PAGE_SIZE));
  const pagedEvents = sortedEvents.slice((eventsPage - 1) * EVENTS_PAGE_SIZE, eventsPage * EVENTS_PAGE_SIZE);

  const toggleSort = (field: typeof sortField) => {
    if (sortField === field) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    else { setSortField(field); setSortDir('desc'); }
    setEventsPage(1);
  };

  const sevColor = (s: string) =>
    s === 'critical' ? { bg: 'bg-red-900/50', border: 'border-red-500/50', text: 'text-red-300', badge: 'bg-red-900/60 text-red-300 border-red-700/50' }
                     : { bg: 'bg-amber-900/30', border: 'border-amber-500/40', text: 'text-amber-300', badge: 'bg-amber-900/50 text-amber-300 border-amber-700/40' };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">

      {/* Header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 border-b border-indigo-500/20 sticky top-0 z-50">
        <div className="px-4 sm:px-8 lg:px-20 py-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg sm:text-2xl font-bold text-white">Alert Events</h1>
            <p className="text-xs text-slate-400">Real-time out-of-range tracking with duration reporting</p>
          </div>
        </div>
      </div>

      <div className="px-4 sm:px-8 lg:px-20 py-6 space-y-5">

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Active', value: activeCount, color: 'text-red-400', bg: 'bg-red-900/20 border-red-700/30' },
            { label: 'Critical', value: criticalCount, color: 'text-red-300', bg: 'bg-red-900/30 border-red-600/40' },
            { label: 'Resolved', value: resolvedCount, color: 'text-emerald-400', bg: 'bg-emerald-900/20 border-emerald-700/30' },
            { label: 'Total', value: events.length, color: 'text-white', bg: 'bg-slate-700/30 border-slate-600/30' },
          ].map(s => (
            <div key={s.label} className={`rounded-xl border p-4 ${s.bg}`}>
              <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
              <div className="text-xs text-slate-400 mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-slate-700">
          {(['events', 'report'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-5 py-2 text-sm font-semibold capitalize border-b-2 transition ${
                tab === t ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-white'
              }`}>
              {t === 'events' ? '📋 Events' : '📊 Report'}
            </button>
          ))}
        </div>

        {/* Controls */}
        <div className="flex flex-wrap gap-3 items-center">
          <select value={hours}
            onChange={e => { const h = Number(e.target.value); setHours(h); tab === 'events' ? fetchEvents(h, filter, severityFilter) : fetchReport(h); }}
            className="px-3 py-1.5 bg-slate-800 border border-slate-600 text-white rounded-lg text-sm focus:outline-none">
            {HOURS_OPTIONS.map(h => (
              <option key={h} value={h}>{h < 24 ? `Last ${h}h` : h === 24 ? 'Last 24h' : h === 48 ? 'Last 2 days' : 'Last 7 days'}</option>
            ))}
          </select>

          {tab === 'events' && <>
            <div className="flex gap-1">
              {(['all', 'active', 'resolved'] as const).map(f => (
                <button key={f} onClick={() => { setFilter(f); setEventsPage(1); fetchEvents(hours, f, severityFilter); }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize ${filter === f ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}>
                  {f}
                </button>
              ))}
            </div>
            <div className="flex gap-1">
              {(['all', 'warning', 'critical'] as const).map(s => (
                <button key={s} onClick={() => { setSeverityFilter(s); setEventsPage(1); fetchEvents(hours, filter, s); }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize ${
                    severityFilter === s
                      ? s === 'critical' ? 'bg-red-600 text-white' : s === 'warning' ? 'bg-amber-600 text-white' : 'bg-indigo-600 text-white'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                  }`}>
                  {s}
                </button>
              ))}
            </div>
          </>}
          <button onClick={() => setExportOpen(true)}
            className="ml-auto px-4 py-1.5 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-sm font-semibold">
             Export PDF
          </button>
        </div>

        <ReportExportModal
          open={exportOpen}
          onClose={() => setExportOpen(false)}
          availableParams={availableParams}
          mode="alerts"
        />

        {loading ? (
          <div className="text-center py-16 text-slate-400">Loading…</div>
        ) : tab === 'events' ? (

          /* ── EVENTS TABLE ── */
          events.length === 0 ? (
            <div className="text-center py-16 bg-slate-800/40 border border-slate-700 rounded-xl">
              <p className="text-slate-400">No alert events found.</p>
              <p className="text-slate-600 text-xs mt-2">Configure alert ranges on the Parameters page.</p>
            </div>
          ) : (
            <div className="bg-slate-800/50 border border-slate-700 rounded-2xl overflow-hidden overflow-x-auto">
              <table className="w-full min-w-[800px] text-sm">
                <thead className="bg-slate-700/50 border-b border-slate-600">
                  <tr>
                    {[
                      { label: '', field: null },
                      { label: 'Parameter', field: 'parameter_name' },
                      { label: 'Severity', field: 'severity' },
                      { label: 'Value / Peak', field: null },
                      { label: 'Range', field: null },
                      { label: 'Start Time', field: 'triggered_at' },
                      { label: 'End Time', field: null },
                      { label: 'Duration', field: 'duration_seconds' },
                    ].map(({ label, field }) => (
                      <th key={label}
                        className={`px-4 py-3 text-left text-xs font-semibold text-slate-300 whitespace-nowrap ${
                          field ? 'cursor-pointer hover:text-white select-none' : ''
                        }`}
                        onClick={() => field && toggleSort(field as typeof sortField)}>
                        {label}
                        {field && sortField === field && (
                          <span className="ml-1">{sortDir === 'desc' ? '▼' : '▲'}</span>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/40">
                  {pagedEvents.map((ev, idx) => {
                    const c = sevColor(ev.severity);
                    return (
                      <tr key={`${ev.id}-${idx}`} className={`transition-colors ${ev.active ? c.bg : 'hover:bg-slate-700/20'}`}>
                        <td className="px-4 py-3">
                          <div className={`w-2 h-2 rounded-full ${ev.active ? (ev.severity === 'critical' ? 'bg-red-500 animate-pulse' : 'bg-amber-400 animate-pulse') : 'bg-emerald-500'}`} />
                        </td>
                        <td className="px-4 py-3 font-semibold text-white">{ev.parameter_name}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-bold border ${c.badge}`}>
                            {ev.severity.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`font-mono font-bold ${ev.active ? c.text : 'text-slate-300'}`}>
                            {ev.value_at_trigger.toFixed(2)}
                          </span>
                          {ev.peak_value !== ev.value_at_trigger && (
                            <span className="text-xs text-slate-500 ml-1">peak: {ev.peak_value?.toFixed(2)}</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-xs font-mono text-slate-400">
                          {ev.alert_min ?? '—'} – {ev.alert_max ?? '—'}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-400">{fmtTime(ev.triggered_at)}</td>
                        <td className="px-4 py-3 text-xs">
                          {ev.resolved_at
                            ? <span className="text-emerald-400">{fmtTime(ev.resolved_at)}</span>
                            : <span className={`font-semibold ${c.text}`}>Still active</span>}
                        </td>
                        <td className="px-4 py-3 text-xs font-semibold text-slate-300">{ev.duration_label}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700 text-xs text-slate-400">
                <span>{sortedEvents.length} events · page {eventsPage} of {totalEventPages}</span>
                <div className="flex gap-1">
                  <button onClick={() => setEventsPage(1)} disabled={eventsPage === 1}
                    className="px-2 py-1 rounded bg-slate-700 disabled:opacity-40 hover:bg-slate-600">«</button>
                  <button onClick={() => setEventsPage(p => Math.max(1, p - 1))} disabled={eventsPage === 1}
                    className="px-2 py-1 rounded bg-slate-700 disabled:opacity-40 hover:bg-slate-600">‹</button>
                  <button onClick={() => setEventsPage(p => Math.min(totalEventPages, p + 1))} disabled={eventsPage === totalEventPages}
                    className="px-2 py-1 rounded bg-slate-700 disabled:opacity-40 hover:bg-slate-600">›</button>
                  <button onClick={() => setEventsPage(totalEventPages)} disabled={eventsPage === totalEventPages}
                    className="px-2 py-1 rounded bg-slate-700 disabled:opacity-40 hover:bg-slate-600">»</button>
                </div>
              </div>
            </div>
          )

        ) : (

          /* ── REPORT ── */
          report.length === 0 ? (
            <div className="text-center py-16 bg-slate-800/40 border border-slate-700 rounded-xl">
              <p className="text-slate-400">No alert data for this period.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {report.map(row => (
                <div key={row.parameter_id} className="bg-slate-800/50 border border-slate-700 rounded-2xl overflow-hidden">
                  {/* Summary header */}
                  <button className="w-full text-left px-6 py-4 flex flex-wrap items-center gap-4"
                    onClick={() => setExpandedParam(expandedParam === row.parameter_id ? null : row.parameter_id)}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-white font-bold text-base">{row.parameter_name}</span>
                        {row.active_events > 0 && (
                          <span className="px-2 py-0.5 bg-red-900/60 text-red-300 border border-red-700/50 rounded-full text-xs font-bold animate-pulse">
                            {row.active_events} ACTIVE
                          </span>
                        )}
                        {row.critical_events > 0 && (
                          <span className="px-2 py-0.5 bg-red-900/40 text-red-400 border border-red-800/40 rounded-full text-xs">
                            {row.critical_events} critical
                          </span>
                        )}
                        {row.warning_events > 0 && (
                          <span className="px-2 py-0.5 bg-amber-900/40 text-amber-400 border border-amber-800/40 rounded-full text-xs">
                            {row.warning_events} warning
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        Range: {row.alert_min ?? '—'} – {row.alert_max ?? '—'}
                      </div>
                    </div>

                    {/* Stats grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                      {[
                        { label: 'Events', value: row.total_events, color: 'text-white' },
                        { label: 'Max reached', value: row.max_value_reached?.toFixed(2) ?? '—', color: 'text-red-400' },
                        { label: 'Min reached', value: row.min_value_reached?.toFixed(2) ?? '—', color: 'text-amber-400' },
                        { label: 'Avg duration', value: fmtDur(row.avg_duration_s), color: 'text-slate-300' },
                      ].map(s => (
                        <div key={s.label} className="bg-slate-700/40 rounded-lg px-3 py-2">
                          <div className={`text-sm font-bold ${s.color}`}>{s.value}</div>
                          <div className="text-xs text-slate-500">{s.label}</div>
                        </div>
                      ))}
                    </div>

                    <span className="text-slate-500 text-xs">{expandedParam === row.parameter_id ? '▲' : '▼'}</span>
                  </button>

                  {/* Mini chart */}
                  <div className="px-6 pb-3">
                    <MiniBarChart events={row.events} alertMin={row.alert_min} alertMax={row.alert_max} />
                  </div>

                  {/* Expanded event list */}
                  {expandedParam === row.parameter_id && (
                    <div className="border-t border-slate-700 overflow-x-auto">
                      <table className="w-full min-w-[600px] text-xs">
                        <thead className="bg-slate-700/40">
                          <tr>
                            {['Severity', 'Value', 'Peak', 'Start', 'End', 'Duration'].map(h => (
                              <th key={h} className="px-4 py-2 text-left text-slate-400 font-semibold">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-700/30">
                          {row.events.map((ev, idx) => {
                            const c = sevColor(ev.severity);
                            return (
                              <tr key={`${row.parameter_id}-${ev.id}-${idx}`} className={ev.active ? c.bg : ''}>
                                <td className="px-4 py-2">
                                  <span className={`px-1.5 py-0.5 rounded text-xs font-bold border ${c.badge}`}>
                                    {ev.severity.toUpperCase()}
                                  </span>
                                </td>
                                <td className={`px-4 py-2 font-mono font-bold ${c.text}`}>{ev.value_at_trigger.toFixed(2)}</td>
                                <td className="px-4 py-2 font-mono text-slate-300">{ev.peak_value?.toFixed(2) ?? '—'}</td>
                                <td className="px-4 py-2 text-slate-400">{fmtTime(ev.triggered_at)}</td>
                                <td className="px-4 py-2">
                                  {ev.resolved_at
                                    ? <span className="text-emerald-400">{fmtTime(ev.resolved_at)}</span>
                                    : <span className={`font-semibold ${c.text}`}>Active</span>}
                                </td>
                                <td className="px-4 py-2 font-semibold text-slate-300">{ev.duration_label}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )
        )}
      </div>
    </div>
  );
}
