'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useMqttStatus } from '@/hooks/useMqttStatus';

interface Parameter { id: number; name: string; enabled: boolean; unit: string; description: string; }

const API    = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
const COLORS = ['#4f46e5','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#ec4899','#84cc16'];
const MAX_HISTORY = 20;
const POST_SAVE_COOLDOWN_MS = 8000;

export default function EditValuesContent() {
  const router = useRouter();
  const { connectionState, getStatusLabel, getStatusColor } = useMqttStatus();

  const [parameters,   setParameters]   = useState<Parameter[]>([]);
  const [values,       setValues]       = useState<Record<number, number>>({});
  const [history,      setHistory]      = useState<Record<number, number[]>>({});
  const [editingId,    setEditingId]    = useState<number | null>(null);
  const [editInput,    setEditInput]    = useState('');
  const [saving,       setSaving]       = useState(false);
  const [msg,          setMsg]          = useState<{ type: 'ok'|'err'; text: string }|null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [isAuthorized, setIsAuthorized] = useState(false);

  const editingIdRef  = useRef<number | null>(null);
  const pollPausedRef = useRef(false);
  const cooldownRef   = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const token   = localStorage.getItem('token');
    const userStr = localStorage.getItem('user');
    if (!token || !userStr) { router.push('/login'); return; }
    const role = (JSON.parse(userStr).role || '').toLowerCase();
    if (role !== 'admin') { router.push('/dashboard'); return; }
    setIsAuthorized(true);
    setCheckingAuth(false);
  }, [router]);

  const pushHistory = useCallback((id: number, val: number) => {
    setHistory(prev => {
      const arr = [...(prev[id] || []), val].slice(-MAX_HISTORY);
      return { ...prev, [id]: arr };
    });
  }, []);

  const fetchLatest = useCallback(async () => {
    if (pollPausedRef.current) return;
    const token = localStorage.getItem('token');
    try {
      const res = await fetch(`${API}/api/parameter-stream/latest`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const data = await res.json();
      (data.parameters || []).forEach((p: any) => {
        const id  = p.parameter_id as number;
        const val = p.value        as number;
        setValues(prev => ({ ...prev, [id]: val }));
        pushHistory(id, val);
      });
    } catch {}
  }, [pushHistory]);

  useEffect(() => {
    if (!isAuthorized) return;
    const token = localStorage.getItem('token');

    fetch(`${API}/api/parameters`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(data => setParameters((data?.parameters || []).filter((p: Parameter) => p.enabled)))
      .catch(() => {});

    fetchLatest();
    const poll = setInterval(fetchLatest, 3000);
    return () => {
      clearInterval(poll);
      if (cooldownRef.current) clearTimeout(cooldownRef.current);
    };
  }, [isAuthorized, fetchLatest]);

  const handleSave = async (paramId: number) => {
    const value = parseFloat(editInput);
    if (isNaN(value)) { setMsg({ type: 'err', text: 'Enter a valid number' }); return; }

    setSaving(true); setMsg(null);
    const { mqttParameters } = await import('@/services/mqttBridgeService');
    const result = await mqttParameters.setValue(paramId, value);

    if (result.ok) {
      setValues(prev => ({ ...prev, [paramId]: value }));
      pushHistory(paramId, value);
      editingIdRef.current = null;
      pollPausedRef.current = false;
      setEditingId(null);
      setEditInput('');
      pollPausedRef.current = true;
      if (cooldownRef.current) clearTimeout(cooldownRef.current);
      cooldownRef.current = setTimeout(() => {
        pollPausedRef.current = false;
      }, POST_SAVE_COOLDOWN_MS);
      setMsg({ type: 'ok', text: `Saved ${value} successfully` });
      setTimeout(() => setMsg(null), 4000);
    } else {
      setMsg({ type: 'err', text: result.error || 'Failed to save value' });
    }
    setSaving(false);
  };

  const handleEditClick = (paramId: number) => {
    editingIdRef.current = paramId;
    pollPausedRef.current = true;
    if (cooldownRef.current) clearTimeout(cooldownRef.current);
    setEditingId(paramId);
    setEditInput(String(values[paramId] ?? ''));
    setMsg(null);
  };

  const handleCancel = (_paramId: number) => {
    editingIdRef.current = null;
    pollPausedRef.current = false;
    setEditingId(null);
    setEditInput('');
  };

  const MiniBarChart = ({ paramId, color }: { paramId: number; color: string }) => {
    const bars = history[paramId] || [];
    if (bars.length === 0) return (
      <div className="h-16 flex items-center justify-center text-slate-600 text-xs">No data yet</div>
    );
    const lo  = Math.min(...bars);
    const hi  = Math.max(...bars);
    const rng = hi - lo;
    return (
      <div className="h-16 flex items-end gap-0.5">
        {bars.map((v, i) => {
          const pct    = rng === 0 ? 60 : Math.max(((v - lo) / rng) * 100, 4);
          const isLast = i === bars.length - 1;
          return (
            <div key={i} className="flex-1 rounded-sm transition-all duration-300"
              style={{
                height: `${pct}%`,
                backgroundColor: isLast ? color : color + '88',
                opacity: 0.6 + (i / bars.length) * 0.4,
              }}
              title={v.toFixed(2)}
            />
          );
        })}
      </div>
    );
  };

  const mqttColors = getStatusColor();
  const mqttLabel  = getStatusLabel();

  if (checkingAuth) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500 mx-auto mb-3" />
        <p className="text-slate-400 text-sm">Checking authorization…</p>
      </div>
    </div>
  );

  if (!isAuthorized) return null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 border-b border-indigo-500/20 sticky top-0 z-50">
        <div className="px-4 sm:px-8 lg:px-20 py-4 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-lg sm:text-2xl font-bold text-white">Edit Parameter Values</h1>
            <p className="text-xs sm:text-sm text-slate-400">Set a value — desktop streams updates via MQTT</p>
          </div>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold
            ${mqttColors.bg} ${mqttColors.border} ${mqttColors.text}`}>
            <span className={`w-2 h-2 rounded-full ${mqttColors.dot} ${connectionState === 'online' ? 'animate-pulse' : ''}`} />
            <span className="hidden sm:inline">Desktop MQTT:</span>
            <span>{mqttLabel}</span>
          </div>
        </div>
      </div>

      <div className="px-4 sm:px-8 lg:px-20 py-8">
        {msg && (
          <div className={`mb-6 px-4 py-3 rounded-lg border text-sm font-semibold
            ${msg.type === 'ok'
              ? 'bg-emerald-900/30 border-emerald-500/40 text-emerald-300'
              : 'bg-red-900/30 border-red-500/40 text-red-300'}`}>
            {msg.type === 'ok' ? '✓' : '✗'} {msg.text}
          </div>
        )}

        {parameters.length === 0 ? (
          <div className="text-center py-16 bg-slate-800/40 rounded-xl border border-slate-700">
            <p className="text-slate-400 mb-4">No enabled parameters found.</p>
            <button onClick={() => router.push('/parameters')}
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold">
              Go to Parameters
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {parameters.map((param, i) => {
              const color     = COLORS[i % COLORS.length];
              const current   = values[param.id];
              const isEditing = editingId === param.id;
              return (
                <div key={param.id}
                  className="bg-slate-800/60 border border-slate-700 rounded-2xl p-5 flex flex-col gap-3 hover:border-slate-600 transition-all">

                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-white">{param.name}</h3>
                      {param.description && <p className="text-xs text-slate-500 mt-0.5">{param.description}</p>}
                    </div>
                  </div>

                  <div className="rounded-xl p-4 text-center"
                    style={{ backgroundColor: color + '18', border: `1px solid ${color}33` }}>
                    <p className="text-xs text-slate-400 font-semibold uppercase tracking-widest mb-1">Current Value</p>
                    <p className="text-4xl font-bold tabular-nums" style={{ color }}>
                      {current !== undefined ? current.toFixed(2) : '—'}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">{param.unit}</p>
                  </div>

                  <MiniBarChart paramId={param.id} color={color} />

                  {isEditing ? (
                    <div className="space-y-2">
                      <label className="text-xs text-slate-400 font-semibold uppercase tracking-widest">
                        New Value ({param.unit})
                      </label>
                      <input
                        type="text"
                        inputMode="decimal"
                        value={editInput}
                        onChange={e => setEditInput(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') handleSave(param.id);
                          if (e.key === 'Escape') handleCancel(param.id);
                        }}
                        autoFocus
                        disabled={saving}
                        className="w-full px-3 py-2 bg-slate-700 border-2 border-indigo-500 rounded-lg text-white font-semibold text-sm focus:outline-none"
                      />
                      <div className="flex gap-2">
                        <button onClick={() => handleSave(param.id)} disabled={saving}
                          className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold">
                          {saving ? 'Saving…' : '✓ Save'}
                        </button>
                        <button onClick={() => handleCancel(param.id)} disabled={saving}
                          className="px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg text-xs font-bold">
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button onClick={() => handleEditClick(param.id)}
                      className="w-full py-2 rounded-lg text-xs font-bold text-white"
                      style={{ backgroundColor: color }}>
                      ✎ Edit Value
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
