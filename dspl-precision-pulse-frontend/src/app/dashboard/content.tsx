'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useRouter } from 'next/navigation';

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
import ModernDateTimeWidget from '@/components/ModernDateTimeWidget';
import MqttStatusIndicator from '@/components/MqttStatusIndicator';
import { useSocketIO } from '@/hooks/useSocketIO';
import { useMqttStatus } from '@/hooks/useMqttStatus';
import { socketIOService } from '@/services/socketIOService';

interface Parameter {
  id: number;
  name: string;
  enabled: boolean;
  unit: string;
  description: string;
  alert_min?: number | null;
  alert_max?: number | null;
  warn_min?: number | null;
  warn_max?: number | null;
}

interface TelemetryData {
  [key: string]: number;
  timestamp: number;
}

interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  label: string;
  value: string;
  time: string;
  color: string;
}

const PARAM_COLORS = [
  '#6439ff', '#54d7ff', '#f472b6', '#a78bfa',
  '#fb923c', '#34d399', '#ef4444', '#8b5cf6',
  '#06b6d4', '#10b981', '#f59e0b', '#ec4899',
];

// ── Module-level telemetry store — survives page navigation ──────────────────
let _telemetryHistory: TelemetryData[] = [];
let _latestData: TelemetryData = { timestamp: Date.now() };
let _prevValues: { [key: string]: number } = {};
let _maxChartPoints = 50;

export default function DashboardContent() {
  const router = useRouter();
  const [user, setUser]                         = useState<any>(null);
  const [parameters, setParameters]             = useState<Parameter[]>([]);
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetryData[]>(_telemetryHistory);
  const [latestData, setLatestData]             = useState<TelemetryData>(_latestData);
  const [prevValues, setPrevValues]             = useState<{ [key: string]: number }>(_prevValues);
  const [tooltip, setTooltip]                   = useState<TooltipState>({ visible: false, x: 0, y: 0, label: '', value: '', time: '', color: '#000' });
  const [isDataStale, setIsDataStale]           = useState(false);
  const [maxChartPoints, setMaxChartPoints]     = useState(_maxChartPoints);
  const [syncBanner, setSyncBanner]             = useState<{ type: 'info' | 'warn' | 'error' | 'success'; msg: string } | null>(null);
  const [alertToasts, setAlertToasts]           = useState<{ id: number; msg: string; type: 'heat' | 'storm' | 'alert' }[]>([]);

  const { socket }                                                    = useSocketIO();
  const { isConnected: isMqttConnected, connectionState, syncStatus, isLoading } = useMqttStatus();

  // Dismiss banner after 6 s
  const bannerTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showBanner = useCallback((type: 'info' | 'warn' | 'error' | 'success', msg: string) => {
    setSyncBanner({ type, msg });
    if (bannerTimer.current) clearTimeout(bannerTimer.current);
    bannerTimer.current = setTimeout(() => setSyncBanner(null), 6000);
  }, []);

  // ── React to connection state changes ──────────────────────────────────────
  const prevConnectionState = useRef(connectionState);
  useEffect(() => {
    const prev = prevConnectionState.current;
    prevConnectionState.current = connectionState;

    if (connectionState === 'offline' && prev !== 'offline') {
      showBanner('warn', '⚠ MQTT disconnected — data buffering locally');
      // Keep last known data visible — do NOT clear history
    }
    if (connectionState === 'reconnecting') {
      showBanner('info', '↻ Reconnecting to MQTT broker…');
    }
    if (connectionState === 'online' && prev === 'reconnecting') {
      showBanner('success', '✓ MQTT reconnected — streaming resumed');
    }
  }, [connectionState, showBanner]);

  // ── React to sync_status events ────────────────────────────────────────────
  useEffect(() => {
    if (syncStatus.status === 'failed') {
      showBanner('error', `✗ Sync failed: ${syncStatus.error ?? 'unknown error'}`);
    } else if (syncStatus.status === 'synced' && (syncStatus.flushed ?? 0) > 0) {
      showBanner('success', `✓ Flushed ${syncStatus.flushed} buffered records to backend`);
    } else if (syncStatus.status === 'reconnected' && (syncStatus.unsynced ?? 0) > 0) {
      showBanner('info', `↻ Syncing ${syncStatus.unsynced} buffered records…`);
    }
  }, [syncStatus, showBanner]);

  // ── Config fetch on mount ──────────────────────────────────────────────────
  useEffect(() => {
    const token = localStorage.getItem('token');
    fetch(`${BACKEND}/api/telemetry/config`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.max_chart_data_points) {
          const pts = Number(data.max_chart_data_points);
          _maxChartPoints = pts;
          setMaxChartPoints(pts);
        }
      })
      .catch(() => {});

    socketIOService.connectIfNeeded();
    const handleConfigUpdate = (data: any) => {
      if (data.key === 'MAX_CHART_DATA_POINTS') {
        const pts = Number(data.value);
        _maxChartPoints = pts;
        setMaxChartPoints(pts);
      }
    };
    socketIOService.on('config_update', handleConfigUpdate);
    return () => socketIOService.off('config_update', handleConfigUpdate);
  }, []);

  // ── Load parameters + seed latest values from REST ───────────────────────
  const loadParameters = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND}/api/parameters`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setParameters((data.parameters || []).filter((p: Parameter) => p.enabled));
      }
    } catch { /* ignore */ }

    // Seed latest values so cards show data immediately before first Socket.IO event
    try {
      const res = await fetch(`${BACKEND}/api/parameter-stream/latest`);
      if (res.ok) {
        const data = await res.json();
        const params: any[] = data?.parameters || [];
        if (params.length) {
          const seeded: TelemetryData = { timestamp: Date.now() };
          // /api/parameter-stream/latest returns { parameter_id, value }
          params.forEach((p: any) => { seeded[String(p.parameter_id ?? p.id)] = p.value; });
          _latestData = seeded;
          setLatestData(seeded);
        }
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    const token    = localStorage.getItem('token');
    const userData = localStorage.getItem('user');
    if (!token) { router.push('/login'); return; }
    if (userData) setUser(JSON.parse(userData));
    // Only clear module-level data if this is a fresh login (no existing history)
    // so charts continue streaming when navigating away and back.
    if (_telemetryHistory.length === 0) {
      _latestData = { timestamp: Date.now() };
      _prevValues = {};
      setLatestData({ timestamp: Date.now() });
      setPrevValues({});
    } else {
      // Restore existing history into React state so charts resume immediately
      setTelemetryHistory([..._telemetryHistory]);
      setLatestData({ ..._latestData });
      setPrevValues({ ..._prevValues });
    }
    loadParameters();
  }, [router, loadParameters]);

  useEffect(() => {
    const onFocus = () => loadParameters();
    window.addEventListener('focus', onFocus);
    // Reload parameters when desktop adds/removes/toggles them
    socketIOService.on('parameter_created', loadParameters);
    socketIOService.on('parameter_updated', loadParameters);
    socketIOService.on('parameter_deleted', loadParameters);
    return () => {
      window.removeEventListener('focus', onFocus);
      socketIOService.off('parameter_created', loadParameters);
      socketIOService.off('parameter_updated', loadParameters);
      socketIOService.off('parameter_deleted', loadParameters);
    };
  }, [loadParameters]);

  // ── Alert toast listener ──────────────────────────────────────────────────
  useEffect(() => {
    socketIOService.connectIfNeeded();
    const handleAlert = (data: any) => {
      const msg = data.message || `⚠ Alert: ${data.parameter_name} = ${data.current_value} (range: ${data.alert_min ?? '—'} – ${data.alert_max ?? '—'})`;
      const type = msg.toLowerCase().includes('heat') ? 'heat'
                 : msg.toLowerCase().includes('storm') ? 'storm'
                 : 'alert';
      const id = Date.now();
      setAlertToasts(prev => [...prev, { id, msg, type }]);
      setTimeout(() => setAlertToasts(prev => prev.filter(t => t.id !== id)), 8000);
    };
    socketIOService.on('alert_triggered', handleAlert);
    return () => { socketIOService.off('alert_triggered', handleAlert); };
  }, []);

  // ── data_stale / data_fresh ────────────────────────────────────────────────
  useEffect(() => {
    if (!socket) return;
    const onStale = () => setIsDataStale(true);
    const onFresh = () => setIsDataStale(false);
    socket.on('data_stale', onStale);
    socket.on('data_fresh', onFresh);
    return () => { socket.off('data_stale', onStale); socket.off('data_fresh', onFresh); };
  }, [socket]);

  // ── Always-on telemetry listener ───────────────────────────────────────────
  useEffect(() => {
    socketIOService.connectIfNeeded();
    const lastParamTs: Record<string, number> = {};
    // Throttle React state updates — batch incoming telemetry and flush at 2fps
    let pendingData: TelemetryData | null = null;
    const flushTimer = setInterval(() => {
      if (!pendingData) return;
      const snap = pendingData;
      pendingData = null;
      _prevValues = { ..._latestData };
      _latestData = snap;
      _telemetryHistory = [..._telemetryHistory, snap].slice(-_maxChartPoints);
      setPrevValues({ ..._prevValues });
      setLatestData({ ..._latestData });
      setTelemetryHistory([..._telemetryHistory]);
    }, 500); // flush at most every 500ms (2fps) — smooth enough, far less DOM work

    const handleTelemetry = (data: any) => {
      const params: any[] = data?.data?.parameters || data?.parameters || [];
      if (!params.length) return;
      const now = Date.now();
      const newData: TelemetryData = { ...(pendingData ?? _latestData), timestamp: now };
      let changed = false;
      params.forEach((p: any) => {
        const id  = String(p.parameter_id ?? p.id ?? '');
        const val = parseFloat(p.value);
        if (!id || id === 'undefined' || isNaN(val)) return;
        if (now - (lastParamTs[id] ?? 0) < 50) return;
        lastParamTs[id] = now;
        newData[id] = val;
        changed = true;
      });
      if (!changed) return;
      pendingData = newData;
    };

    const handleAdminEdit = (data: any) => {
      const id  = String(data?.parameter_id ?? '');
      const val = parseFloat(data?.value);
      if (!id || id === 'undefined' || isNaN(val)) return;
      // Admin edits apply immediately (not throttled)
      const newData: TelemetryData = { ..._latestData, timestamp: Date.now(), [id]: val };
      _prevValues = { ..._latestData };
      _latestData = newData;
      _telemetryHistory = [..._telemetryHistory, newData].slice(-_maxChartPoints);
      setPrevValues({ ..._prevValues });
      setLatestData({ ..._latestData });
      setTelemetryHistory([..._telemetryHistory]);
    };

    socketIOService.on('telemetry', handleTelemetry);
    socketIOService.on('parameter_stream_update', handleTelemetry);
    socketIOService.on('parameter_value_updated', handleAdminEdit);

    return () => {
      clearInterval(flushTimer);
      socketIOService.off('telemetry', handleTelemetry);
      socketIOService.off('parameter_stream_update', handleTelemetry);
      socketIOService.off('parameter_value_updated', handleAdminEdit);
    };
  }, []);

  // ── Helpers ────────────────────────────────────────────────────────────────
  const getChartColor = useCallback((_: number, index: number) =>
    PARAM_COLORS[index % PARAM_COLORS.length], []);

  const getTrendIndicator = useCallback((paramId: number) => {
    const id      = String(paramId);
    const current = latestData[id] ?? 0;
    const prev    = prevValues[id] ?? current;
    if (current >= prev + 0.1) return { symbol: '▲', color: '#49e7b5' };
    if (current <  prev - 0.1) return { symbol: '▼', color: '#f16363' };
    return { symbol: '', color: '#64748b' };
  }, [latestData, prevValues]);

  const handlePointHover = useCallback((
    e: React.MouseEvent<SVGCircleElement>,
    label: string, value: number, timestamp: number, color: string,
  ) => {
    const rect = (e.currentTarget as SVGCircleElement).getBoundingClientRect();
    setTooltip({
      visible: true,
      x: rect.left + rect.width / 2,
      y: rect.top,
      label, value: value.toFixed(2),
      time: new Date(timestamp).toLocaleTimeString(),
      color,
    });
  }, []);

  const renderLineChart = useCallback((
    rawData: (number | undefined)[], color: string, label: string, timestamps: number[], unit: string,
    paramId: string,
  ) => {
    const paired = rawData
      .map((v, i) => ({ v, t: timestamps[i] }))
      .filter(pt => pt.v !== undefined && !isNaN(pt.v as number)) as { v: number; t: number }[];

    if (paired.length < 2) return (
      <div className="h-40 flex items-center justify-center text-slate-500 text-sm">
        Collecting data…
      </div>
    );

    const values = paired.map(pt => pt.v);
    const times  = paired.map(pt => pt.t);

    const maxV = Math.max(...values);
    const minV = Math.min(...values);
    const rawRange = maxV - minV;
    // 10% padding; if all values identical use 10% of value itself (min 1)
    const padding = rawRange * 0.1 || Math.abs(maxV) * 0.1 || 1;
    const hi = maxV + padding;
    const lo = minV - padding;
    const range = hi - lo;

    const pad = { top: 40, right: 80, bottom: 36, left: 60 };
    const W = 800, H = 220;
    const iW = W - pad.left - pad.right;
    const iH = H - pad.top  - pad.bottom;

    const toX = (i: number) =>
      paired.length === 1
        ? pad.left + iW / 2
        : pad.left + (i / (paired.length - 1)) * iW;
    const toY = (v: number) => pad.top + iH - ((v - lo) / range) * iH;

    const points = paired.map((pt, i) => ({ x: toX(i), y: toY(pt.v), value: pt.v, timestamp: pt.t }));
    const pathD  = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    const last   = points[points.length - 1];
    const first  = points[0];

    const yTicks = Array.from({ length: 5 }, (_, i) => lo + (range * i / 4));

    const xTickCount = Math.min(6, paired.length);
    const xTicks = xTickCount === 1
      ? [{ x: toX(0), label: new Date(times[0]).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }]
      : Array.from({ length: xTickCount }, (_, i) => {
          const idx = Math.round(i * (paired.length - 1) / (xTickCount - 1));
          return {
            x: toX(idx),
            label: new Date(times[idx]).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          };
        });

    return (
      <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-4">
        <div className="flex justify-between items-center mb-3">
          <span className="text-slate-200 font-semibold text-sm">{label}</span>
          <span className="font-bold text-base" style={{ color }}>
            {values[values.length - 1].toFixed(2)} {unit}
          </span>
        </div>
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" className="overflow-visible">
          {yTicks.map((v, i) => {
            const y = toY(v);
            return (
              <g key={i}>
                <line x1={pad.left} y1={y} x2={W - pad.right} y2={y}
                  stroke="#334155" strokeWidth="1" strokeDasharray="4 4" />
                <text x={pad.left - 8} y={y + 4} textAnchor="end" fontSize="11" fill="#64748b">
                  {v.toFixed(1)}
                </text>
              </g>
            );
          })}
          {xTicks.map((t, i) => (
            <text key={i} x={t.x} y={H - 4} textAnchor="middle" fontSize="10" fill="#64748b">
              {t.label}
            </text>
          ))}
          <path
            d={`${pathD} L${last.x.toFixed(1)},${(pad.top + iH).toFixed(1)} L${first.x.toFixed(1)},${(pad.top + iH).toFixed(1)} Z`}
            fill={color} fillOpacity="0.12"
          />
          <path d={pathD} fill="none" stroke={color} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" />
          {/* Render all points: small visible dot + large invisible hover target */}
          {points.map((p, i) => {
            const isLatest = i === points.length - 1;
            return (
              <g key={i}>
                <circle cx={p.x} cy={p.y} r={isLatest ? 5 : 3}
                  fill={isLatest ? color : color + '99'} stroke={color} strokeWidth={isLatest ? 2 : 1}
                  style={{ pointerEvents: 'none' }}
                />
                {/* Large invisible hit area for hover */}
                <circle cx={p.x} cy={p.y} r="12" fill="transparent"
                  style={{ cursor: 'crosshair' }}
                  onMouseEnter={e => handlePointHover(e, label, p.value, p.timestamp, color)}
                  onMouseLeave={() => setTooltip(t => ({ ...t, visible: false }))}
                />
              </g>
            );
          })}
        </svg>
      </div>
    );
  }, [handlePointHover]);

  // ── Offline / stale state ─────────────────────────────────────────────────────────
  // Don't treat as offline while the initial MQTT status fetch is still in-flight
  const isOffline           = !isLoading && !isMqttConnected;
  const isUnexpectedlyStale = isMqttConnected && isDataStale;

  // ── Memoised cards ─────────────────────────────────────────────────────────
  const dataCards = useMemo(() => parameters.map((param, index) => {
    const trend   = getTrendIndicator(param.id);
    const color   = getChartColor(param.id, index);
    const idStr   = String(param.id);
    const current = latestData[idStr];

    const isCritical = current !== undefined && !isOffline && (
      (param.alert_min != null && current < param.alert_min) ||
      (param.alert_max != null && current > param.alert_max)
    );
    const isWarning = !isCritical && current !== undefined && !isOffline && (
      (param.warn_min != null && current < param.warn_min) ||
      (param.warn_max != null && current > param.warn_max)
    );
    const outOfRange = isCritical || isWarning;

    const cardBorder  = isCritical ? 'from-red-950 to-slate-900 border-red-500/60'
                      : isWarning  ? 'from-amber-950 to-slate-900 border-amber-500/50'
                      : '';
    const valueGrad   = isCritical ? 'linear-gradient(to right,#ef4444,#dc2626)'
                      : isWarning  ? 'linear-gradient(to right,#f59e0b,#d97706)'
                      : `linear-gradient(to right,${color},${color}cc)`;
    const barColor    = isOffline ? '#334155' : isCritical ? '#ef4444' : isWarning ? '#f59e0b' : color;
    const labelColor  = isCritical ? 'text-red-400' : isWarning ? 'text-amber-400' : 'text-slate-400';
    const badgeText   = isCritical ? '⚠ CRITICAL' : '⚡ WARNING';
    const badgeCls    = isCritical
      ? 'text-red-400 bg-red-900/40 border-red-700/50'
      : 'text-amber-400 bg-amber-900/40 border-amber-700/50';
    const rangeMin    = isCritical ? param.alert_min : param.warn_min;
    const rangeMax    = isCritical ? param.alert_max : param.warn_max;

    return (
      <div key={param.id}
        className={`bg-gradient-to-br rounded-3xl p-6 shadow-lg border transition-all
          ${ isOffline
              ? 'from-slate-800 to-slate-900 border-slate-700/40 opacity-40 pointer-events-none grayscale'
              : isCritical ? 'from-red-950/60 to-slate-900 border-red-500/60'
              : isWarning  ? 'from-amber-950/40 to-slate-900 border-amber-500/50'
              : isUnexpectedlyStale
              ? 'from-slate-800 to-slate-900 border-slate-700 opacity-60'
              : 'from-slate-800 to-slate-900 border-slate-700 hover:border-slate-600 card-glow' }`}
      >
        <div className="flex justify-between items-start mb-2">
          {/* Value — plain red when critical, amber when warning, gradient otherwise */}
          <div
            className="text-6xl font-bold tabular-nums"
            style={current !== undefined && !isOffline ? (
              isCritical ? { color: '#ef4444' } :
              isWarning  ? { color: '#f59e0b' } :
              { backgroundImage: valueGrad, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', color: 'transparent' }
            ) : { color: '#475569' }}
          >
            {current !== undefined ? current.toFixed(1) : '—'}
          </div>
          <div className="flex flex-col items-end gap-1">
            {/* Alert icon — shown prominently when critical */}
            {isCritical && (
              <span className="text-2xl animate-pulse" title="CRITICAL ALERT">⚠️</span>
            )}
            {isWarning && !isCritical && (
              <span className="text-2xl" title="WARNING">⚡</span>
            )}
            {!outOfRange && !isOffline && trend.symbol && (
              <div style={{ color: trend.color }} className="text-3xl">{trend.symbol}</div>
            )}
            {isOffline && <div className="text-slate-600 text-2xl">⏸</div>}
            {outOfRange && (
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full border animate-pulse ${badgeCls}`}>
                {badgeText}
              </span>
            )}
          </div>
        </div>
        <div className={`text-sm mb-1 font-medium ${labelColor}`}>
          {param.name} ({param.unit})
        </div>
        {outOfRange && (rangeMin != null || rangeMax != null) && (
          <div className={`text-xs mb-3 ${isCritical ? 'text-red-500' : 'text-amber-500'}`}>
            Range: {rangeMin ?? '—'} – {rangeMax ?? '—'} | Current: {current?.toFixed(2)}
          </div>
        )}
        <div className="h-16 flex items-end gap-1">
          {telemetryHistory.slice(-Math.min(maxChartPoints, 14)).map((d, i, arr) => {
            const v    = d[idStr] ?? 0;
            const vals = arr.map(x => x[idStr] ?? 0);
            const lo   = Math.min(...vals), hi = Math.max(...vals);
            const rng  = hi - lo;
            const height = rng === 0 ? (hi > 0 ? 60 : 5) : Math.max(((v - lo) / rng) * 100, 5);
            return (
              <div key={i} className="flex-1"
                style={{
                  height: `${height}%`,
                  backgroundColor: barColor,
                  opacity: isOffline ? 0.3 : 0.5 + (i / arr.length) * 0.5,
                }}
                title={`${v.toFixed(2)} ${param.unit}`}
              />
            );
          })}
        </div>
      </div>
    );
  }), [parameters, latestData, telemetryHistory, getTrendIndicator, getChartColor, isMqttConnected, isDataStale, maxChartPoints]);

  const lineCharts = useMemo(() => parameters.map((param, index) => {
    const color = getChartColor(param.id, index);
    const idStr = String(param.id);
    return (
      <div key={param.id}
        className={`bg-gradient-to-br from-slate-800 to-slate-900 rounded-3xl p-4 shadow-lg border border-slate-700
          ${ isOffline
              ? 'opacity-30 pointer-events-none grayscale'
              : isUnexpectedlyStale
              ? 'opacity-50 pointer-events-none'
              : '' }`}
      >
        {renderLineChart(
          telemetryHistory.map(d => d[idStr] !== undefined ? d[idStr] : undefined),
          isOffline ? '#475569' : color, param.name,
          telemetryHistory.map(d => d.timestamp),
          param.unit,
          idStr,
        )}
      </div>
    );
  }), [parameters, telemetryHistory, maxChartPoints, getChartColor, renderLineChart, isMqttConnected, isDataStale]);

  if (!user) return null;

  // ── Banner colours ─────────────────────────────────────────────────────────
  const bannerStyle: Record<string, string> = {
    info:    'bg-blue-900/80 border-blue-500/50 text-blue-200',
    warn:    'bg-amber-900/80 border-amber-500/50 text-amber-200',
    error:   'bg-red-900/80 border-red-500/50 text-red-200',
    success: 'bg-emerald-900/80 border-emerald-500/50 text-emerald-200',
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">

      {/* ── FULL-SCREEN FROZEN OVERLAY when MQTT is offline ── */}
      {isOffline && (
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center"
          style={{ background: 'rgba(2,6,23,0.85)', backdropFilter: 'blur(6px)' }}
        >
          <div className="text-center px-8 max-w-sm">
            {/* Icon */}
            <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center mx-auto mb-5">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
            </div>
            {/* Title */}
            <h2 className="text-2xl font-bold text-white mb-2">Stream Frozen</h2>
            <p className="text-slate-400 text-sm leading-relaxed mb-5">
              MQTT disconnected — data generation stopped on desktop.
              <br/>New readings are buffering to local SQLite storage.
            </p>
            {/* Status row */}
            <div className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800/80 border border-slate-700 text-xs text-slate-400">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
              </span>
              Waiting for MQTT broker to reconnect…
            </div>
            {/* Buffering note */}
            <p className="text-slate-600 text-xs mt-3">
              Data will auto-sync to web when connection restores
            </p>
          </div>
        </div>
      )}

      {/* ── Status banner ── */}
      {syncBanner && (
        <div className={`fixed top-0 left-0 right-0 z-[100] flex items-center justify-between
          px-6 py-2 border-b text-sm font-semibold ${bannerStyle[syncBanner.type]}`}
        >
          <span>{syncBanner.msg}</span>
          <button onClick={() => setSyncBanner(null)} className="ml-4 opacity-70 hover:opacity-100">✕</button>
        </div>
      )}

      {/* ── Header ── */}
      <div className={`bg-gradient-to-r from-slate-900 to-slate-800 border-b border-indigo-500/20 sticky z-50
        ${syncBanner ? 'top-8' : 'top-0'}`}
      >
        <div className="px-4 sm:px-8 py-4 flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 lg:gap-3">
          <div className="flex items-center gap-4">
            <img src="/logo.svg" alt="PrecisionPulse Logo" className="w-8 h-8 sm:w-12 sm:h-12" />
            <div>
              <h1 className="text-lg sm:text-2xl font-bold text-white">Dashboard</h1>
              <p className="text-xs sm:text-sm text-slate-400">Real-time Telemetry</p>
            </div>
          </div>
          <div className="hidden lg:block"><ModernDateTimeWidget /></div>
          <div className="flex items-center gap-3">
            <MqttStatusIndicator showLabel showTooltip size="md" />
          </div>
        </div>
      </div>

      {/* ── Content ── */}
      <div className="px-4 sm:px-8 lg:px-20 py-12">
        <div className="mb-8">
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-2">
            Welcome back, {user.name}!
          </h2>
          <p className="text-slate-400 text-base sm:text-lg lg:text-xl">
            {isOffline ? 'Stream paused — last known values shown below' : 'Monitor your telemetry streams in real-time'}
          </p>
        </div>

        {/* Live Data Stream */}
        <div className="mb-12">
          <div className="flex items-center gap-2 mb-4">
            <span className={`w-2 h-2 rounded-full ${isOffline ? 'bg-amber-500' : 'bg-emerald-500 animate-pulse'}`} />
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
              {isOffline ? 'Last Known Values (Frozen)' : 'Live Data Stream'}
            </h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {dataCards}
          </div>
        </div>

        {/* Historical Trends */}
        <div>
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Historical Trends</h3>
          <div className="space-y-6">{lineCharts}</div>
        </div>
      </div>

      {/* Alert Toasts — top-right corner, rendered in portal to escape overflow:hidden */}
      {alertToasts.length > 0 && typeof document !== 'undefined' && createPortal(
        <div style={{
          position: 'fixed', top: '20px', right: '20px', zIndex: 2147483647,
          display: 'flex', flexDirection: 'column', gap: '10px', width: '340px',
          pointerEvents: 'auto',
        }}>
          {alertToasts.map(toast => {
            const isCrit = toast.type === 'heat' || toast.msg.toLowerCase().includes('critical');
            return (
              <div key={toast.id} style={{
                display: 'flex', alignItems: 'flex-start', gap: '10px',
                padding: '12px 14px', borderRadius: '12px',
                boxShadow: '0 8px 32px rgba(0,0,0,0.9)',
                fontSize: '13px', fontWeight: 600,
                backgroundColor: isCrit ? 'rgba(127,29,29,0.98)' : 'rgba(120,53,15,0.98)',
                border: isCrit ? '1px solid #ef4444' : '1px solid #f59e0b',
                color: isCrit ? '#fee2e2' : '#fef3c7',
              }}>
                <span style={{ fontSize: '16px', flexShrink: 0, marginTop: '1px' }}>
                  {isCrit ? '⚠️' : '⚡'}
                </span>
                <span style={{ flex: 1, lineHeight: 1.4 }}>{toast.msg}</span>
                <button onClick={() => setAlertToasts(prev => prev.filter(t => t.id !== toast.id))}
                  style={{ flexShrink: 0, opacity: 0.7, fontSize: '14px', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: '0 2px' }}>
                  ✕
                </button>
              </div>
            );
          })}
        </div>,
        document.body
      )}

      {/* Tooltip — rendered via portal so it escapes overflow:hidden */}
      {tooltip.visible && typeof document !== 'undefined' && createPortal(
        <div style={{
          position: 'fixed',
          left: tooltip.x,
          top: tooltip.y - 90,
          transform: 'translateX(-50%)',
          zIndex: 2147483647,
          pointerEvents: 'none',
          background: '#0f172a',
          border: `2px solid ${tooltip.color}`,
          borderRadius: 8,
          padding: '8px 12px',
          fontSize: 13,
          fontWeight: 600,
          boxShadow: '0 8px 24px rgba(0,0,0,0.8)',
          minWidth: 140,
          whiteSpace: 'nowrap',
        }}>
          <div style={{ color: tooltip.color }}>{tooltip.label}</div>
          <div style={{ color: '#fff', fontSize: 15, fontWeight: 700, margin: '2px 0' }}>{tooltip.value}</div>
          <div style={{ color: '#64748b', fontSize: 11 }}>{tooltip.time}</div>
        </div>,
        document.body
      )}
    </div>
  );
}
