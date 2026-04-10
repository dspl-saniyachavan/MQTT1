'use client';

import { useEffect, useState, useCallback } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { socketIOService } from '@/services/socketIOService';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

interface Parameter {
  id: number;
  name: string;
  enabled: boolean;
  unit: string;
  description: string;
  alert_min: number | null;
  alert_max: number | null;
  warn_min: number | null;
  warn_max: number | null;
}

const sort = (params: Parameter[]) =>
  [...params].sort((a, b) =>
    a.enabled === b.enabled ? a.name.localeCompare(b.name) : a.enabled ? -1 : 1
  );

function ParametersPageContent() {
  const [parameters, setParameters] = useState<Parameter[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [alertParam, setAlertParam] = useState<Parameter | null>(null);
  const [formData, setFormData] = useState({ name: '', unit: '', description: '' });
  const [alertForm, setAlertForm] = useState({ alert_min: '', alert_max: '', warn_min: '', warn_max: '' });
  const [error, setError] = useState('');
  const [alertError, setAlertError] = useState('');
  const [loading, setLoading] = useState(false);
  const [paramPage, setParamPage] = useState(1);
  const PARAM_PAGE_SIZE = 15;

  // ── Initial fetch ──────────────────────────────────────────────────────────
  const fetchParameters = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${BACKEND_URL}/api/parameters`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setParameters(sort(data.parameters || []));
      }
    } catch { /* ignore */ }
  }, []);

  // ── Socket.IO delta handlers — zero full-refetch ───────────────────────────
  useEffect(() => {
    fetchParameters();
    socketIOService.connectIfNeeded();

    const onCreated = (data: any) => {
      const p: Parameter = data.parameter ?? data;
      setParameters(prev => sort(prev.some(x => x.id === p.id) ? prev : [...prev, p]));
    };

    const onUpdated = (data: any) => {
      const p: Parameter = data.parameter ?? data;
      setParameters(prev => sort(prev.map(x => x.id === p.id ? { ...x, ...p } : x)));
    };

    const onDeleted = (data: any) => {
      const id = data.parameter_id ?? data.parameter?.id ?? data.id;
      setParameters(prev => prev.filter(x => x.id !== id));
    };

    socketIOService.on('parameter_created', onCreated);
    socketIOService.on('parameter_updated', onUpdated);
    socketIOService.on('parameter_deleted', onDeleted);

    return () => {
      socketIOService.off('parameter_created', onCreated);
      socketIOService.off('parameter_updated', onUpdated);
      socketIOService.off('parameter_deleted', onDeleted);
    };
  }, [fetchParameters]);

  // ── Toggle enabled/disabled — optimistic + MQTT with full param payload ────
  const toggleParameter = async (param: Parameter) => {
    const newEnabled = !param.enabled;
    // Optimistic update immediately
    setParameters(prev => sort(prev.map(p => p.id === param.id ? { ...p, enabled: newEnabled } : p)));

    try {
      const token = localStorage.getItem('token');
      // Use REST directly for immediate reliable update
      const res = await fetch(`${BACKEND_URL}/api/parameters/${param.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ enabled: newEnabled }),
      });
      if (!res.ok) {
        // Revert on failure
        setParameters(prev => sort(prev.map(p => p.id === param.id ? { ...p, enabled: param.enabled } : p)));
      }
      // Socket.IO parameter_updated will propagate to desktop and other web clients
    } catch {
      setParameters(prev => sort(prev.map(p => p.id === param.id ? { ...p, enabled: param.enabled } : p)));
    }
  };

  // ── Add parameter via MQTT bridge ──────────────────────────────────────────
  const addParameter = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { mqttParameters } = await import('@/services/mqttBridgeService');
      const result = await mqttParameters.create(formData);
      if (result.ok) {
        setShowAddModal(false);
        setFormData({ name: '', unit: '', description: '' });
        // parameter_created Socket.IO event will add it to state
      } else {
        setError(result.error || 'Failed to add parameter');
      }
    } catch { setError('Network error'); }
    finally { setLoading(false); }
  };

  // ── Remove parameter via MQTT bridge ──────────────────────────────────────
  const removeParameter = async (id: number) => {
    if (!confirm('Remove this parameter?')) return;
    // Optimistic remove
    setParameters(prev => prev.filter(p => p.id !== id));
    const { mqttParameters } = await import('@/services/mqttBridgeService');
    const result = await mqttParameters.delete(id);
    if (!result.ok) fetchParameters(); // revert on failure
  };

  // ── Alert range ────────────────────────────────────────────────────────────
  const openAlertModal = (param: Parameter) => {
    setAlertParam(param);
    setAlertForm({
      alert_min: param.alert_min != null ? String(param.alert_min) : '',
      alert_max: param.alert_max != null ? String(param.alert_max) : '',
      warn_min:  param.warn_min  != null ? String(param.warn_min)  : '',
      warn_max:  param.warn_max  != null ? String(param.warn_max)  : '',
    });
    setAlertError('');
  };

  const saveAlertRange = async () => {
    if (!alertParam) return;
    setAlertError('');
    const parse = (s: string) => s.trim() === '' ? null : parseFloat(s);
    const minVal  = parse(alertForm.alert_min);
    const maxVal  = parse(alertForm.alert_max);
    const warnMin = parse(alertForm.warn_min);
    const warnMax = parse(alertForm.warn_max);
    if (minVal !== null && isNaN(minVal))   { setAlertError('Critical min must be a number'); return; }
    if (maxVal !== null && isNaN(maxVal))   { setAlertError('Critical max must be a number'); return; }
    if (warnMin !== null && isNaN(warnMin)) { setAlertError('Warning min must be a number'); return; }
    if (warnMax !== null && isNaN(warnMax)) { setAlertError('Warning max must be a number'); return; }
    if (minVal !== null && maxVal !== null && minVal >= maxVal) { setAlertError('Critical min must be less than max'); return; }
    if (warnMin !== null && warnMax !== null && warnMin >= warnMax) { setAlertError('Warning min must be less than max'); return; }

    // Optimistic update
    setParameters(prev => prev.map(p =>
      p.id === alertParam.id ? { ...p, alert_min: minVal, alert_max: maxVal, warn_min: warnMin, warn_max: warnMax } : p
    ));
    setAlertParam(null);

    const { mqttParameters } = await import('@/services/mqttBridgeService');
    const result = await mqttParameters.setAlertRange(alertParam.id, minVal, maxVal, warnMin, warnMax);
    if (!result.ok) {
      setAlertError(result.error || 'Failed to save alert range');
      fetchParameters(); // revert
    }
  };

  const enabledCount = parameters.filter(p => p.enabled).length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 border-b border-indigo-500/20 sticky top-0 z-50">
        <div className="px-4 sm:px-8 lg:px-20 py-4">
          <h1 className="text-lg sm:text-2xl font-bold text-white">Parameter Configuration</h1>
          <p className="text-xs sm:text-sm text-slate-400">Configure parameters and alert ranges</p>
        </div>
      </div>

      <div className="px-4 sm:px-8 lg:px-20 py-8">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
          <div>
            <h2 className="text-2xl sm:text-4xl font-bold text-white mb-1">Telemetry Parameters</h2>
            <p className="text-slate-400 text-sm">Configure which parameters the desktop collects and their alert ranges</p>
          </div>
          <button onClick={() => setShowAddModal(true)}
            className="w-full sm:w-auto px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg text-sm">
            + Add Parameter
          </button>
        </div>

        <div className="bg-indigo-900/30 border border-indigo-500/30 rounded-lg px-4 py-3 mb-6 text-indigo-200 text-sm">
          <strong>{enabledCount}</strong> of <strong>{parameters.length}</strong> parameters enabled.
          Values outside the configured alert range will be highlighted in red on the dashboard.
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-2xl overflow-hidden overflow-x-auto">
          <table className="w-full min-w-[700px] text-sm">
            <thead className="bg-slate-700/50 border-b border-slate-600">
              <tr>
                <th className="px-5 py-3 text-left text-slate-300 font-semibold">Status</th>
                <th className="px-5 py-3 text-left text-slate-300 font-semibold">Parameter</th>
                <th className="px-5 py-3 text-left text-slate-300 font-semibold">Unit</th>
                <th className="px-5 py-3 text-left text-slate-300 font-semibold">Alert Range</th>
                <th className="hidden lg:table-cell px-5 py-3 text-left text-slate-300 font-semibold">Description</th>
                <th className="px-5 py-3 text-right text-slate-300 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {parameters.slice((paramPage - 1) * PARAM_PAGE_SIZE, paramPage * PARAM_PAGE_SIZE).map(param => {
                const hasRange = param.alert_min != null || param.alert_max != null;
                const hasWarn  = param.warn_min  != null || param.warn_max  != null;
                const rangeText = param.alert_min != null && param.alert_max != null
                  ? `${param.alert_min} – ${param.alert_max}`
                  : param.alert_min != null ? `≥ ${param.alert_min}`
                  : param.alert_max != null ? `≤ ${param.alert_max}` : 'Not set';
                const warnText = param.warn_min != null && param.warn_max != null
                  ? `${param.warn_min} – ${param.warn_max}`
                  : param.warn_min != null ? `≥ ${param.warn_min}`
                  : param.warn_max != null ? `≤ ${param.warn_max}` : null;
                return (
                  <tr key={param.id} className="hover:bg-slate-700/20 transition-colors">
                    <td className="px-5 py-4">
                      <button onClick={() => toggleParameter(param)}
                        className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                          param.enabled
                            ? 'bg-emerald-900/40 text-emerald-300 hover:bg-emerald-900/60'
                            : 'bg-red-900/40 text-red-400 hover:bg-red-900/60'
                        }`}>
                        {param.enabled ? '✓ Enabled' : '✗ Disabled'}
                      </button>
                    </td>
                    <td className="px-5 py-4 text-white font-medium">{param.name}</td>
                    <td className="px-5 py-4 text-slate-400">{param.unit}</td>
                    <td className="px-5 py-4">
                      <div className="flex flex-col gap-1">
                        <span className={`text-xs font-mono px-2 py-0.5 rounded ${
                          hasRange ? 'bg-red-900/40 text-red-300 border border-red-700/40' : 'text-slate-500'
                        }`}>
                          {hasRange ? `⚠ ${rangeText}` : 'Not set'}
                        </span>
                        {warnText && (
                          <span className="text-xs font-mono px-2 py-0.5 rounded bg-amber-900/30 text-amber-300 border border-amber-700/30">
                            ⚡ {warnText}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="hidden lg:table-cell px-5 py-4 text-slate-500 text-xs">{param.description}</td>
                    <td className="px-5 py-4 text-right space-x-2">
                      <button onClick={() => openAlertModal(param)}
                        className="px-3 py-1 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-xs font-semibold">
                        Set Alert
                      </button>
                      <button onClick={() => removeParameter(param.id)}
                        className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold">
                        Remove
                      </button>
                    </td>
                  </tr>
                );
              })}
              {parameters.length === 0 && (
                <tr><td colSpan={6} className="px-5 py-10 text-center text-slate-500">No parameters configured yet.</td></tr>
              )}
            </tbody>
          </table>
          {parameters.length > PARAM_PAGE_SIZE && (
            <div className="px-5 py-3 flex items-center justify-between border-t border-slate-700/50">
              <span className="text-slate-500 text-xs">Page {paramPage} of {Math.ceil(parameters.length / PARAM_PAGE_SIZE)} · {parameters.length} parameters</span>
              <div className="flex gap-1">
                <button onClick={() => setParamPage(p => Math.max(1, p - 1))} disabled={paramPage === 1}
                  className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 text-slate-300 rounded text-xs font-semibold">Prev</button>
                {Array.from({ length: Math.min(5, Math.ceil(parameters.length / PARAM_PAGE_SIZE)) }, (_, i) => {
                  const total = Math.ceil(parameters.length / PARAM_PAGE_SIZE);
                  const start = Math.max(1, Math.min(paramPage - 2, total - 4));
                  const n = start + i;
                  return n <= total ? (
                    <button key={n} onClick={() => setParamPage(n)}
                      className={`px-2 py-1 rounded text-xs font-semibold ${paramPage === n ? 'bg-indigo-600 text-white' : 'bg-slate-700 hover:bg-slate-600 text-slate-300'}`}>{n}</button>
                  ) : null;
                })}
                <button onClick={() => setParamPage(p => Math.min(Math.ceil(parameters.length / PARAM_PAGE_SIZE), p + 1))}
                  disabled={paramPage === Math.ceil(parameters.length / PARAM_PAGE_SIZE)}
                  className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 text-slate-300 rounded text-xs font-semibold">Next</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Add Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl p-8 max-w-md w-full shadow-2xl">
            <h3 className="text-xl font-bold text-white mb-6">Add New Parameter</h3>
            <form onSubmit={addParameter} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Parameter Name</label>
                <input type="text" value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-indigo-500 focus:outline-none"
                  placeholder="e.g., Temperature" required disabled={loading} />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Unit</label>
                <input type="text" value={formData.unit} onChange={e => setFormData({ ...formData, unit: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-indigo-500 focus:outline-none"
                  placeholder="e.g., °C, kPa" required disabled={loading} />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Description</label>
                <textarea value={formData.description} onChange={e => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-indigo-500 focus:outline-none"
                  rows={3} placeholder="Brief description" required disabled={loading} />
              </div>
              {error && <p className="text-red-400 text-xs">{error}</p>}
              <div className="flex gap-3 pt-2">
                <button type="submit" disabled={loading}
                  className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-semibold rounded-lg text-sm">
                  {loading ? 'Adding…' : 'Add Parameter'}
                </button>
                <button type="button" onClick={() => { setShowAddModal(false); setFormData({ name: '', unit: '', description: '' }); setError(''); }}
                  className="flex-1 py-2.5 bg-slate-600 hover:bg-slate-700 text-white font-semibold rounded-lg text-sm">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Alert Modal */}
      {alertParam && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl p-8 max-w-md w-full shadow-2xl">
            <h3 className="text-xl font-bold text-white mb-1">Set Alert Thresholds</h3>
            <p className="text-slate-400 text-sm mb-5">
              <span className="text-violet-300 font-semibold">{alertParam.name}</span> ({alertParam.unit})
            </p>
            <div className="space-y-5">
              <div className="bg-red-900/20 border border-red-700/30 rounded-xl p-4 space-y-3">
                <div className="text-xs font-bold text-red-400 uppercase tracking-wider">⚠ Critical Range</div>
                <p className="text-xs text-slate-500">Value outside this range triggers a CRITICAL alert.</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Min (alert if below)</label>
                    <input type="number" step="any" value={alertForm.alert_min}
                      onChange={e => setAlertForm({ ...alertForm, alert_min: e.target.value })}
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-red-500 focus:outline-none" placeholder="e.g., 10" />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Max (alert if above)</label>
                    <input type="number" step="any" value={alertForm.alert_max}
                      onChange={e => setAlertForm({ ...alertForm, alert_max: e.target.value })}
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-red-500 focus:outline-none" placeholder="e.g., 80" />
                  </div>
                </div>
              </div>
              <div className="bg-amber-900/20 border border-amber-700/30 rounded-xl p-4 space-y-3">
                <div className="text-xs font-bold text-amber-400 uppercase tracking-wider">⚡ Warning Range</div>
                <p className="text-xs text-slate-500">Value outside this range (but inside critical) triggers a WARNING alert.</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Min (warn if below)</label>
                    <input type="number" step="any" value={alertForm.warn_min}
                      onChange={e => setAlertForm({ ...alertForm, warn_min: e.target.value })}
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-amber-500 focus:outline-none" placeholder="e.g., 20" />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Max (warn if above)</label>
                    <input type="number" step="any" value={alertForm.warn_max}
                      onChange={e => setAlertForm({ ...alertForm, warn_max: e.target.value })}
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-amber-500 focus:outline-none" placeholder="e.g., 60" />
                  </div>
                </div>
              </div>
              {alertError && <p className="text-red-400 text-xs">{alertError}</p>}
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={saveAlertRange}
                className="flex-1 py-2.5 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-lg text-sm">Save</button>
              <button onClick={() => setAlertParam(null)}
                className="flex-1 py-2.5 bg-slate-600 hover:bg-slate-700 text-white font-semibold rounded-lg text-sm">Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ParametersContent() {
  return (
    <ProtectedRoute allowedRoles={['admin']}>
      <ParametersPageContent />
    </ProtectedRoute>
  );
}
