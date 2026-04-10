'use client';

import { useState, useRef, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
const COLORS = ['#6366f1', '#22d3ee', '#f59e0b', '#10b981', '#f43f5e', '#a78bfa', '#34d399', '#fb923c'];

export interface AvailableParam { id: number; name: string; unit: string; }

interface Props {
  open: boolean;
  onClose: () => void;
  availableParams: AvailableParam[];
  mode: 'telemetry' | 'alerts';
}

interface SeriesPoint { t: string; v: number; }
interface Series { parameter_id: number; name: string; unit: string; data: SeriesPoint[]; }

function buildChartRows(series: Series[]) {
  const map = new Map<string, Record<string, any>>();
  for (const s of series) {
    for (const pt of s.data) {
      const label = pt.t;
      if (!map.has(label)) map.set(label, { label });
      map.get(label)![s.name] = pt.v;
    }
  }
  return Array.from(map.values()).sort((a, b) =>
    new Date(a.label).getTime() - new Date(b.label).getTime()
  );
}

// ── Draw a multi-line chart onto a canvas using pure Canvas 2D ───────────────
function drawChartToCanvas(
  series: Series[],
  canvasW: number,
  canvasH: number,
  title: string
): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = canvasW;
  canvas.height = canvasH;
  const ctx = canvas.getContext('2d')!;

  const PAD = { top: 40, right: 30, bottom: 50, left: 60 };
  const plotW = canvasW - PAD.left - PAD.right;
  const plotH = canvasH - PAD.top - PAD.bottom;

  // Background
  ctx.fillStyle = '#0f172a';
  ctx.fillRect(0, 0, canvasW, canvasH);

  // Title
  ctx.fillStyle = '#e2e8f0';
  ctx.font = 'bold 14px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(title, canvasW / 2, 22);

  // Collect all timestamps and values
  const allTimes: number[] = [];
  let globalMin = Infinity, globalMax = -Infinity;
  for (const s of series) {
    for (const pt of s.data) {
      allTimes.push(new Date(pt.t).getTime());
      if (pt.v < globalMin) globalMin = pt.v;
      if (pt.v > globalMax) globalMax = pt.v;
    }
  }
  if (!allTimes.length) return canvas;

  const tMin = Math.min(...allTimes);
  const tMax = Math.max(...allTimes);
  const vRange = globalMax - globalMin || 1;
  const vMin = globalMin - vRange * 0.05;
  const vMax = globalMax + vRange * 0.05;

  const toX = (t: number) => PAD.left + ((t - tMin) / (tMax - tMin || 1)) * plotW;
  const toY = (v: number) => PAD.top + plotH - ((v - vMin) / (vMax - vMin)) * plotH;

  // Grid lines
  ctx.strokeStyle = '#1e293b';
  ctx.lineWidth = 1;
  const yTicks = 5;
  for (let i = 0; i <= yTicks; i++) {
    const v = vMin + (i / yTicks) * (vMax - vMin);
    const y = toY(v);
    ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(PAD.left + plotW, y); ctx.stroke();
    ctx.fillStyle = '#64748b';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(v.toFixed(1), PAD.left - 6, y + 3);
  }

  // X axis ticks (5 labels)
  const xTicks = 5;
  for (let i = 0; i <= xTicks; i++) {
    const t = tMin + (i / xTicks) * (tMax - tMin);
    const x = toX(t);
    ctx.beginPath(); ctx.strokeStyle = '#1e293b'; ctx.moveTo(x, PAD.top); ctx.lineTo(x, PAD.top + plotH); ctx.stroke();
    ctx.fillStyle = '#64748b';
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'center';
    const label = new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    ctx.fillText(label, x, PAD.top + plotH + 14);
  }

  // Axes
  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(PAD.left, PAD.top);
  ctx.lineTo(PAD.left, PAD.top + plotH);
  ctx.lineTo(PAD.left + plotW, PAD.top + plotH);
  ctx.stroke();

  // Lines per series
  for (let si = 0; si < series.length; si++) {
    const s = series[si];
    if (!s.data.length) continue;
    const color = COLORS[si % COLORS.length];
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    let first = true;
    for (const pt of s.data) {
      const x = toX(new Date(pt.t).getTime());
      const y = toY(pt.v);
      if (first) { ctx.moveTo(x, y); first = false; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  // Legend
  const legendY = canvasH - 16;
  let legendX = PAD.left;
  ctx.font = '11px sans-serif';
  ctx.textAlign = 'left';
  for (let si = 0; si < series.length; si++) {
    const color = COLORS[si % COLORS.length];
    ctx.fillStyle = color;
    ctx.fillRect(legendX, legendY - 8, 16, 3);
    ctx.fillStyle = '#94a3b8';
    ctx.fillText(series[si].name, legendX + 20, legendY);
    legendX += ctx.measureText(series[si].name).width + 40;
    if (legendX > canvasW - 60) break;
  }

  return canvas;
}

export default function ReportExportModal({ open, onClose, availableParams, mode }: Props) {
  const today = new Date().toISOString().slice(0, 10);
  const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);

  const [fromDate, setFromDate] = useState(weekAgo);
  const [toDate, setToDate] = useState(today);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewSeries, setPreviewSeries] = useState<Series[]>([]);
  const [error, setError] = useState('');

  const toggleParam = (id: number) =>
    setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  const fetchSeries = useCallback(async (): Promise<Series[]> => {
    const token = localStorage.getItem('token') || '';
    const ids = selectedIds.length ? selectedIds : availableParams.map(p => p.id);
    const start = new Date(fromDate).toISOString();
    const end = new Date(toDate + 'T23:59:59').toISOString();

    if (mode === 'telemetry') {
      const qs = ids.map(id => `param_ids=${id}`).join('&');
      const res = await fetch(
        `${BACKEND}/api/reports/parameter-history?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}&${qs}&limit=2000`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const json = await res.json();
      return (json.series || []) as Series[];
    } else {
      const res = await fetch(
        `${BACKEND}/api/alert-events?hours=99999&start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const json = await res.json();
      const evts: any[] = json.events || [];
      const grouped = new Map<number, Series>();
      for (const ev of evts) {
        if (ids.length && !ids.includes(ev.parameter_id)) continue;
        if (!grouped.has(ev.parameter_id))
          grouped.set(ev.parameter_id, { parameter_id: ev.parameter_id, name: ev.parameter_name, unit: '', data: [] });
        grouped.get(ev.parameter_id)!.data.push({ t: ev.triggered_at, v: ev.value_at_trigger });
      }
      return Array.from(grouped.values());
    }
  }, [selectedIds, availableParams, fromDate, toDate, mode]);

  const handlePreview = async () => {
    setError(''); setLoading(true);
    try { setPreviewSeries(await fetchSeries()); }
    catch (e: any) { setError(e.message || 'Failed to load data'); }
    finally { setLoading(false); }
  };

  const handleExportPDF = async () => {
    setError(''); setLoading(true);
    try {
      const series = previewSeries.length ? previewSeries : await fetchSeries();
      if (!series.length) { setError('No data for selected range/parameters.'); setLoading(false); return; }

      const { jsPDF } = await import('jspdf');
      const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
      const W = doc.internal.pageSize.getWidth();   // 297
      const H = doc.internal.pageSize.getHeight();  // 210
      let y = 15;

      const newPageIfNeeded = (needed: number) => {
        if (y + needed > H - 10) { doc.addPage(); y = 15; }
      };

      // ── Cover / title ──────────────────────────────────────────────────────
      doc.setFillColor(15, 23, 42);
      doc.rect(0, 0, W, H, 'F');

      doc.setFontSize(22);
      doc.setTextColor(99, 102, 241);
      doc.text('PrecisionPulse', W / 2, y + 4, { align: 'center' });
      y += 10;

      doc.setFontSize(13);
      doc.setTextColor(148, 163, 184);
      doc.text(mode === 'telemetry' ? 'Telemetry Parameter Report' : 'Alert Events Report', W / 2, y, { align: 'center' });
      y += 7;

      doc.setFontSize(10);
      doc.setTextColor(100, 116, 139);
      doc.text(`Period: ${fromDate}  →  ${toDate}`, W / 2, y, { align: 'center' });
      y += 5;
      doc.text(`Generated: ${new Date().toLocaleString()}`, W / 2, y, { align: 'center' });
      y += 10;

      // ── Parameter summary table ────────────────────────────────────────────
      const colW = [W * 0.28, W * 0.08, W * 0.13, W * 0.13, W * 0.13, W * 0.12];
      const colX = colW.reduce<number[]>((acc, w, i) => [...acc, (acc[i] || 10) + (i === 0 ? 0 : colW[i - 1])], [10]);

      // Section header
      doc.setFillColor(30, 41, 59);
      doc.rect(10, y, W - 20, 7, 'F');
      doc.setFontSize(11);
      doc.setTextColor(255, 255, 255);
      doc.text('Parameter Summary', 14, y + 5);
      y += 9;

      // Table header
      doc.setFillColor(51, 65, 85);
      doc.rect(10, y, W - 20, 6, 'F');
      doc.setFontSize(8);
      doc.setTextColor(148, 163, 184);
      ['Parameter', 'Unit', 'Min', 'Max', 'Avg', 'Points'].forEach((h, i) => doc.text(h, colX[i] + 1, y + 4));
      y += 6;

      for (const s of series) {
        const vals = s.data.map(d => d.v);
        if (!vals.length) continue;
        newPageIfNeeded(7);
        const row = [
          s.name.length > 30 ? s.name.slice(0, 28) + '…' : s.name,
          s.unit || '—',
          Math.min(...vals).toFixed(2),
          Math.max(...vals).toFixed(2),
          (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2),
          String(vals.length),
        ];
        doc.setFillColor(15, 23, 42);
        doc.rect(10, y, W - 20, 6, 'F');
        doc.setTextColor(226, 232, 240);
        row.forEach((cell, i) => doc.text(cell, colX[i] + 1, y + 4));
        y += 6;
      }
      y += 6;

      // ── Per-parameter data table ───────────────────────────────────────────
      for (const s of series) {
        if (!s.data.length) continue;
        newPageIfNeeded(20);

        doc.setFillColor(30, 41, 59);
        doc.rect(10, y, W - 20, 7, 'F');
        doc.setFontSize(10);
        doc.setTextColor(255, 255, 255);
        doc.text(`${s.name}${s.unit ? ` (${s.unit})` : ''}  —  ${s.data.length} readings`, 14, y + 5);
        y += 9;

        // Column headers
        const dColW = [W * 0.35, W * 0.25];
        const dColX = [10, 10 + dColW[0]];
        doc.setFillColor(51, 65, 85);
        doc.rect(10, y, W - 20, 5, 'F');
        doc.setFontSize(7.5);
        doc.setTextColor(148, 163, 184);
        doc.text('Timestamp', dColX[0] + 1, y + 3.5);
        doc.text('Value', dColX[1] + 1, y + 3.5);
        y += 5;

        // Show up to 50 rows per parameter to keep PDF manageable
        const rows = s.data.slice(0, 50);
        for (const pt of rows) {
          newPageIfNeeded(5);
          doc.setFillColor(15, 23, 42);
          doc.rect(10, y, W - 20, 5, 'F');
          doc.setTextColor(226, 232, 240);
          doc.text(new Date(pt.t).toLocaleString(), dColX[0] + 1, y + 3.5);
          doc.text(String(pt.v), dColX[1] + 1, y + 3.5);
          y += 5;
        }
        if (s.data.length > 50) {
          doc.setTextColor(100, 116, 139);
          doc.setFontSize(7);
          doc.text(`… and ${s.data.length - 50} more readings`, 14, y + 3.5);
          y += 5;
        }
        y += 4;
      }

      // ── Multi-line chart (all series together) ─────────────────────────────
      if (series.some(s => s.data.length > 0)) {
        doc.addPage();
        y = 15;

        doc.setFillColor(15, 23, 42);
        doc.rect(0, 0, W, H, 'F');

        doc.setFillColor(30, 41, 59);
        doc.rect(10, y, W - 20, 7, 'F');
        doc.setFontSize(11);
        doc.setTextColor(255, 255, 255);
        doc.text('Multi-Parameter Line Chart', 14, y + 5);
        y += 10;

        const chartCanvas = drawChartToCanvas(series, 1100, 500, '');
        const imgData = chartCanvas.toDataURL('image/png');
        const chartH = H - y - 10;
        doc.addImage(imgData, 'PNG', 10, y, W - 20, chartH);
      }

      // ── Individual per-parameter charts ───────────────────────────────────
      for (const s of series) {
        if (s.data.length < 2) continue;
        doc.addPage();
        y = 15;

        doc.setFillColor(15, 23, 42);
        doc.rect(0, 0, W, H, 'F');

        doc.setFillColor(30, 41, 59);
        doc.rect(10, y, W - 20, 7, 'F');
        doc.setFontSize(11);
        doc.setTextColor(255, 255, 255);
        doc.text(`${s.name}${s.unit ? ` (${s.unit})` : ''}`, 14, y + 5);
        y += 10;

        const singleCanvas = drawChartToCanvas([s], 1100, 500, '');
        const imgData = singleCanvas.toDataURL('image/png');
        const chartH = H - y - 10;
        doc.addImage(imgData, 'PNG', 10, y, W - 20, chartH);
      }

      doc.save(`precisionpulse_${mode}_report_${fromDate}_${toDate}.pdf`);
    } catch (e: any) {
      setError(e.message || 'PDF generation failed');
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  const chartRows = buildChartRows(previewSeries);
  const displaySeries = selectedIds.length
    ? previewSeries.filter(s => selectedIds.includes(s.parameter_id))
    : previewSeries;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
          <div>
            <h2 className="text-lg font-bold text-white">Export PDF Report</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {mode === 'telemetry' ? 'Telemetry parameter data' : 'Alert events data'} · summary table + per-param data + charts
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl leading-none">✕</button>
        </div>

        <div className="px-6 py-5 space-y-5">
          {error && <div className="bg-red-900/40 border border-red-500/40 rounded-lg p-3 text-red-300 text-sm">{error}</div>}

          {/* Date range */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">From Date</label>
              <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 text-white rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">To Date</label>
              <input type="date" value={toDate} onChange={e => setToDate(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 text-white rounded-lg text-sm focus:outline-none focus:border-indigo-500" />
            </div>
          </div>

          {/* Parameter selection */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-400">
                Parameters ({selectedIds.length === 0 ? 'all' : `${selectedIds.length} selected`})
              </label>
              <div className="flex gap-3">
                <button onClick={() => setSelectedIds(availableParams.map(p => p.id))}
                  className="text-xs text-indigo-400 hover:text-indigo-300">Select all</button>
                <button onClick={() => setSelectedIds([])}
                  className="text-xs text-slate-500 hover:text-slate-300">Clear</button>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 max-h-28 overflow-y-auto p-2 bg-slate-800/50 rounded-lg border border-slate-700">
              {availableParams.map(p => (
                <button key={p.id} onClick={() => toggleParam(p.id)}
                  className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                    selectedIds.includes(p.id)
                      ? 'bg-indigo-600 border-indigo-500 text-white'
                      : 'bg-slate-700 border-slate-600 text-slate-300 hover:border-indigo-500'
                  }`}>
                  {p.name}{p.unit ? ` (${p.unit})` : ''}
                </button>
              ))}
              {availableParams.length === 0 && <span className="text-slate-500 text-xs">No parameters available</span>}
            </div>
          </div>

          
          <button onClick={handlePreview} disabled={loading}
            className="w-full py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white rounded-lg text-sm font-semibold transition-colors">
            {loading ? 'Loading…' : ' Preview Chart'}
          </button>

          {/* Chart preview */}
          {previewSeries.length > 0 && (
            <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
              <p className="text-xs font-semibold text-slate-400 mb-3">
                Preview — {displaySeries.length} parameter(s) · {chartRows.length} time points
              </p>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={chartRows} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="label" stroke="#64748b" tick={{ fontSize: 9 }}
                    tickFormatter={v => new Date(v).toLocaleDateString()} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 9 }} />
                  <Tooltip
                    contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                    labelStyle={{ color: '#94a3b8', fontSize: 10 }}
                    itemStyle={{ fontSize: 10 }}
                    labelFormatter={v => new Date(v).toLocaleString()}
                  />
                  <Legend wrapperStyle={{ fontSize: 10, color: '#94a3b8' }} />
                  {previewSeries.map((s, i) => (
                    <Line key={s.parameter_id} type="monotone" dataKey={s.name}
                      stroke={COLORS[i % COLORS.length]} dot={false}
                      strokeWidth={2} isAnimationActive={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="flex gap-3 pt-1">
            <button onClick={onClose}
              className="flex-1 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm font-semibold">
              Cancel
            </button>
            <button onClick={handleExportPDF} disabled={loading}
              className="flex-1 py-2.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold transition-colors">
              {loading ? 'Generating PDF…' : ' Download PDF'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
