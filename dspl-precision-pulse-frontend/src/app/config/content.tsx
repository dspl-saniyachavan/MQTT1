'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import RBACGuard from '@/components/RBACGuard';
import { socketIOService } from '@/services/socketIOService';
import { configService, SystemConfig } from '@/services/configService';

interface EditingState {
  configId: number;
  newValue: string;
}

interface NewConfigForm {
  key: string;
  value: string;
  description: string;
  category: string;
  data_type: 'string' | 'integer' | 'boolean' | 'json';
  is_sensitive: boolean;
}

export default function ConfigContent() {
  const router = useRouter();
  const [configs, setConfigs] = useState<SystemConfig[]>([]);
  const [filteredConfigs, setFilteredConfigs] = useState<SystemConfig[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<EditingState | null>(null);
  const [globalVersion, setGlobalVersion] = useState(1);
  const [lastSync, setLastSync] = useState<string>('');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [userRole, setUserRole] = useState<string>('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [newConfig, setNewConfig] = useState<NewConfigForm>({
    key: '',
    value: '',
    description: '',
    category: 'general',
    data_type: 'string',
    is_sensitive: false,
  });
  const [syncStatus, setSyncStatus] = useState<'connected' | 'disconnected' | 'syncing'>('disconnected');
  const [searchTerm, setSearchTerm] = useState('');
  const [configPage, setConfigPage] = useState(1);
  const CONFIG_PAGE_SIZE = 20;

  // Live system config values for the 5 core keys
  const SYSTEM_KEYS = ['TELEMETRY_FETCH_INTERVAL_MS', 'MAX_CHART_DATA_POINTS', 'TELEMETRY_RETENTION_DAYS'] as const;
  type SystemKey = typeof SYSTEM_KEYS[number];
  const [systemValues, setSystemValues] = useState<Record<SystemKey, string>>({
    TELEMETRY_FETCH_INTERVAL_MS: '',
    MAX_CHART_DATA_POINTS: '',
    TELEMETRY_RETENTION_DAYS: '',
  });
  const [systemEditing, setSystemEditing] = useState<SystemKey | null>(null);
  const [systemDraft, setSystemDraft] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('token');
    const userData = localStorage.getItem('user');

    if (!token) {
      router.push('/login');
      return;
    }

    let role = 'user';
    if (userData) {
      try {
        const user = JSON.parse(userData);
        role = user.role || 'user';
      } catch (e) {
        console.error('[CONFIG] Error parsing user data:', e);
      }
    }

    if (role !== 'admin') {
      router.push('/dashboard');
      return;
    }

    setUserRole(role);
    configService.setToken(token);
    loadConfigs();
    loadCategories();
  }, [router]);

  useEffect(() => {
    const handleConfigUpdate = (data: any) => {
      if (SYSTEM_KEYS.includes(data.key as SystemKey)) {
        setSystemValues(prev => ({ ...prev, [data.key]: data.value }));
      }
      showMessage('Configuration updated', 'success');
      loadConfigs();
    };

    const handleConfigBulkUpdate = (data: any) => {
      const updates: Record<string, string> = {};
      (data.configs || []).forEach((c: any) => {
        if (SYSTEM_KEYS.includes(c.key as SystemKey)) updates[c.key] = c.value;
      });
      if (Object.keys(updates).length) setSystemValues(prev => ({ ...prev, ...updates }));
      showMessage('Configurations updated', 'success');
      loadConfigs();
    };

    socketIOService.connectIfNeeded();
    setSyncStatus('connected');
    socketIOService.on('config_update', handleConfigUpdate);
    socketIOService.on('config_bulk_update', handleConfigBulkUpdate);

    return () => {
      socketIOService.off('config_update', handleConfigUpdate);
      socketIOService.off('config_bulk_update', handleConfigBulkUpdate);
    };
  }, []);

  useEffect(() => {
    let filtered = configs.filter(c => !HIDDEN_CONFIG_KEYS.has(c.key.toUpperCase()));

    if (selectedCategory !== 'all') {
      filtered = filtered.filter((c) => c.category === selectedCategory);
    }

    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (c) =>
          c.key.toLowerCase().includes(term) ||
          (c.value ?? '').toLowerCase().includes(term) ||
          (c.description ?? '').toLowerCase().includes(term)
      );
    }

    setFilteredConfigs(filtered);
    setConfigPage(1); // reset to page 1 on filter change
  }, [selectedCategory, configs, searchTerm]);

  const showMessage = (text: string, type: 'success' | 'error') => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 4000);
  };

  const loadConfigs = async () => {
    try {
      setLoading(true);
      const data = await configService.getAllConfigs();
      setConfigs(data.configs || []);
      setGlobalVersion(data.global_version || 1);
      setLastSync(new Date().toLocaleTimeString());
      // Sync system values from loaded configs using functional update to avoid stale closure
      const freshValues: Partial<Record<SystemKey, string>> = {};
      (data.configs || []).forEach((c: any) => {
        if (SYSTEM_KEYS.includes(c.key as SystemKey)) freshValues[c.key as SystemKey] = c.value;
      });
      if (Object.keys(freshValues).length > 0) {
        setSystemValues(prev => ({ ...prev, ...freshValues }));
      }
    } catch (err) {
      console.error('[CONFIG] Error loading configs:', err);
      showMessage(`Failed to load configurations: ${err instanceof Error ? err.message : 'Unknown error'}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadCategories = async () => {
    try {
      const data = await configService.getCategories();
      setCategories(data.categories || []);
    } catch (err) {
      console.error('[CONFIG] Error loading categories:', err);
    }
  };

  const READONLY_CONFIG_KEYS = new Set([
    'MQTT_BROKER', 'AUTO_FLUSH_ENABLED', 'SYNC_ENABLED',
    'SYNC_INTERVAL', 'MQTT_USE_TLS',
    'AUTO_FLUSH_ENABLED', 'BUFFER_SIZE', 'HEARTBEAT_INTERVAL', 'SYNC_INTERVAL',
  ]);
  const HIDDEN_CONFIG_KEYS = new Set(['AUTO_FLUSH_ENABLED', 'BUFFER_SIZE', 'HEARTBEAT_INTERVAL', 'SYNC_INTERVAL', 'MQTT_KEEP_ALIVE']);

  const handleEdit = (config: SystemConfig) => {
    if (READONLY_CONFIG_KEYS.has(config.key.toUpperCase())) return;
    setEditing({ configId: config.id, newValue: config.value });
  };

  const handleSave = async () => {
    if (!editing) return;
    const config = configs.find((c) => c.id === editing.configId);
    if (!config) return;
    try {
      const { mqttConfig } = await import('@/services/mqttBridgeService');
      await mqttConfig.update(config.key, editing.newValue);
      showMessage('Configuration updated', 'success');
      loadConfigs();
      setEditing(null);
    } catch (err) {
      showMessage(`Error updating configuration: ${err instanceof Error ? err.message : 'Unknown error'}`, 'error');
    }
  };

  const handleCancel = () => { setEditing(null); };

  const handleSystemSave = async (key: SystemKey) => {
    try {
      const { mqttConfig } = await import('@/services/mqttBridgeService');
      await mqttConfig.update(key, systemDraft);
      setSystemValues(prev => ({ ...prev, [key]: systemDraft }));
      setSystemEditing(null);
      showMessage(`${key} updated`, 'success');
      loadConfigs();
    } catch (err) {
      showMessage(`Error updating ${key}: ${err instanceof Error ? err.message : 'Unknown error'}`, 'error');
    }
  };

  const handleDelete = async (key: string) => {
    if (!confirm(`Are you sure you want to delete "${key}"?`)) return;
    try {
      await configService.deleteConfig(key); // delete stays HTTP (no MQTT delete handler)
      showMessage('Configuration deleted', 'success');
      loadConfigs();
    } catch (err) {
      showMessage(`Error deleting configuration: ${err instanceof Error ? err.message : 'Unknown error'}`, 'error');
    }
  };

  const handleAddConfig = async () => {
    if (!newConfig.key || !newConfig.value) { showMessage('Key and value are required', 'error'); return; }
    try {
      const { mqttConfig } = await import('@/services/mqttBridgeService');
      await mqttConfig.update(newConfig.key, newConfig.value);
      showMessage('Configuration created', 'success');
      setNewConfig({ key: '', value: '', description: '', category: 'general', data_type: 'string', is_sensitive: false });
      setShowAddForm(false);
      loadConfigs();
    } catch (err) {
      console.error('[CONFIG] Error creating config:', err);
      showMessage(
        `Error creating configuration: ${err instanceof Error ? err.message : 'Unknown error'}`,
        'error'
      );
    }
  };

  return (
    <RBACGuard permission="manage_config" fallback={<div>Access Denied</div>}>
      <div className="min-h-screen bg-slate-900">
        {/* Header */}
        <div className="bg-gradient-to-r from-slate-900 to-slate-800 border-b border-indigo-500/20 sticky top-0 z-50">
          <div className="px-8 py-4 flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-white">System Configuration</h1>
              <p className="text-sm text-slate-400">Manage system settings and parameters</p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={loadConfigs}
                className="px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold transition"
              >
                Refresh
              </button>
            </div>
          </div>
        </div>

        {/* Messages */}
        {message && (
          <div
            className={`mx-8 mt-4 p-4 rounded-lg ${
              message.type === 'success'
                ? 'bg-emerald-900/30 border border-emerald-600 text-emerald-400'
                : 'bg-red-900/30 border border-red-600 text-red-400'
            }`}
          >
            {message.text}
          </div>
        )}

        {/* Main Content */}
        <div className="px-8 py-12">
          {/* Title and Stats */}
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h2 className="text-4xl font-bold text-white mb-2">Configuration Settings</h2>
              <div className="flex gap-6 text-gray-400 text-sm">
                <span>
                  Total: <span className="font-semibold text-white">{filteredConfigs.length}</span>
                </span>
                <span>
                  Version: <span className="font-semibold text-white">{globalVersion}</span>
                </span>
                <span>
                  Last Sync: <span className="font-semibold text-white">{lastSync || 'Never'}</span>
                </span>
                <span className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      syncStatus === 'connected' ? 'bg-emerald-500' : 'bg-red-500'
                    }`}
                  />
                  <span className="font-semibold text-white capitalize">{syncStatus}</span>
                </span>
              </div>
            </div>
          </div>

          {/* System Settings Panel */}
          <div className="mb-8 bg-slate-950 rounded-xl border border-slate-800 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center gap-3">
              <span className="text-lg">⚙️</span>
              <h3 className="text-white font-bold text-lg">System Settings</h3>
              <span className="ml-auto text-xs text-slate-500">Live — changes propagate to desktop instantly</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-0 divide-y md:divide-y-0 md:divide-x divide-slate-800">
              {([
                { key: 'TELEMETRY_FETCH_INTERVAL_MS', label: 'Telemetry Fetch Interval',  unit: 'ms',  type: 'integer', desc: 'Desktop push rate' },
                { key: 'MAX_CHART_DATA_POINTS',       label: 'Max Chart Data Points',     unit: 'pts', type: 'integer', desc: 'Live chart buffer size' },
                { key: 'TELEMETRY_RETENTION_DAYS',    label: 'Telemetry Retention',       unit: 'days',type: 'integer', desc: 'DB retention window' },
              ] as { key: SystemKey; label: string; unit: string; type: string; desc: string }[]).map(({ key, label, unit, type, desc }) => (
                <div key={key} className="px-6 py-5 flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{label}</span>
                    {systemEditing !== key && (
                      <button
                        onClick={() => { setSystemEditing(key); setSystemDraft(systemValues[key]); }}
                        className="text-xs px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded transition"
                      >Edit</button>
                    )}
                  </div>
                  {systemEditing === key ? (
                    <div className="flex gap-2 items-center">
                      <input
                        type={type === 'integer' ? 'number' : 'text'}
                        value={systemDraft}
                        onChange={e => setSystemDraft(e.target.value)}
                        className="flex-1 px-3 py-1.5 bg-slate-800 text-white rounded border border-blue-600 focus:outline-none text-sm"
                        autoFocus
                      />
                      <button onClick={() => handleSystemSave(key)} className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs font-semibold">Save</button>
                      <button onClick={() => setSystemEditing(null)} className="px-3 py-1.5 bg-slate-600 hover:bg-slate-700 text-white rounded text-xs">✕</button>
                    </div>
                  ) : (
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-2xl font-bold text-emerald-400 font-mono">
                        {systemValues[key] || <span className="text-slate-600 text-base">—</span>}
                      </span>
                      {unit && <span className="text-slate-500 text-sm">{unit}</span>}
                    </div>
                  )}
                  <span className="text-xs text-slate-600">{desc}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Search and Filter */}
          <div className="mb-6 flex gap-4">
            <input
              type="text"
              placeholder="Search configurations..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="flex-1 px-4 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 focus:border-blue-600 focus:outline-none"
            />
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-4 py-2 bg-slate-800 text-white rounded-lg border border-slate-700 hover:border-slate-600 transition"
            >
              <option value="all">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          {/* Loading State */}
          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="text-gray-400 mt-4">Loading configurations...</p>
            </div>
          ) : filteredConfigs.length === 0 ? (
            <div className="text-center py-12 bg-slate-950 rounded-lg border border-slate-800">
              <p className="text-gray-400 text-lg">No configurations found</p>
            </div>
          ) : (
            /* Table */
            <div className="bg-slate-950 rounded-lg overflow-hidden border border-slate-800 shadow-lg">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-slate-900 border-b border-slate-800">
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Key</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Value</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Category</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Description</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Type</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Version</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Updated</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {filteredConfigs.slice((configPage - 1) * CONFIG_PAGE_SIZE, configPage * CONFIG_PAGE_SIZE).map((config) => (
                      <tr key={config.id} className="hover:bg-slate-900/50 transition-colors">
                        <td className="px-6 py-4 text-white font-medium font-mono text-sm">{config.key}</td>
                        <td className="px-6 py-4">
                          {editing?.configId === config.id ? (
                            <input
                              type="text"
                              value={editing.newValue}
                              onChange={(e) =>
                                setEditing({ ...editing, newValue: e.target.value })
                              }
                              className="px-3 py-2 bg-slate-800 text-white rounded border border-blue-600 w-full focus:outline-none focus:border-blue-500"
                              autoFocus
                            />
                          ) : (
                            <span
                              className={`font-mono text-sm ${
                                config.is_sensitive ? 'text-gray-500' : 'text-emerald-400'
                              }`}
                            >
                              {config.is_sensitive ? '***' : config.value}
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <span className="px-2 py-1 bg-blue-900/30 text-blue-400 rounded text-xs font-semibold">
                            {config.category}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-gray-400 text-sm max-w-xs truncate">
                          {config.description || '-'}
                        </td>
                        <td className="px-6 py-4">
                          <span className="px-2 py-1 bg-purple-900/30 text-purple-400 rounded text-xs font-semibold">
                            {config.data_type}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="px-2 py-1 bg-yellow-900/30 text-yellow-400 rounded text-xs font-semibold">
                            v{config.version}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-gray-500 text-xs">
                          <div>{new Date(config.updated_at).toLocaleDateString()}</div>
                          <div>{new Date(config.updated_at).toLocaleTimeString()}</div>
                          <div className="text-gray-600 text-xs mt-1">by {config.updated_by || 'system'}</div>
                        </td>
                    <td className="px-6 py-3">
                      {editing?.configId === config.id ? (
                        <div className="flex gap-2">
                          <button onClick={handleSave} className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-sm font-semibold transition">Save</button>
                          <button onClick={handleCancel} className="px-3 py-1 bg-gray-600 hover:bg-gray-700 text-white rounded text-sm font-semibold transition">Cancel</button>
                        </div>
                      ) : READONLY_CONFIG_KEYS.has(config.key.toUpperCase()) ? (
                        <span className="px-2 py-1 bg-slate-700 text-slate-400 rounded text-xs font-semibold flex items-center gap-1 w-fit">🔒 Read-only</span>
                      ) : (
                        <div className="flex gap-2">
                          <button onClick={() => handleEdit(config)} className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-semibold transition">Edit</button>
                          <button onClick={() => handleDelete(config.key)} className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-sm font-semibold transition">Delete</button>
                        </div>
                      )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Pagination */}
              {filteredConfigs.length > CONFIG_PAGE_SIZE && (
                <div className="px-6 py-3 flex items-center justify-between border-t border-slate-800 bg-slate-900/50">
                  <span className="text-slate-500 text-xs">
                    Page {configPage} of {Math.ceil(filteredConfigs.length / CONFIG_PAGE_SIZE)} · {filteredConfigs.length} configs
                  </span>
                  <div className="flex gap-1">
                    <button onClick={() => setConfigPage(1)} disabled={configPage === 1}
                      className="px-2 py-1 rounded text-xs text-slate-400 hover:bg-slate-700 disabled:text-slate-600 disabled:cursor-not-allowed">«</button>
                    <button onClick={() => setConfigPage(p => Math.max(1, p - 1))} disabled={configPage === 1}
                      className="px-2 py-1 rounded text-xs text-slate-400 hover:bg-slate-700 disabled:text-slate-600 disabled:cursor-not-allowed">‹</button>
                    {Array.from({ length: Math.min(5, Math.ceil(filteredConfigs.length / CONFIG_PAGE_SIZE)) }, (_, i) => {
                      const total = Math.ceil(filteredConfigs.length / CONFIG_PAGE_SIZE);
                      const start = Math.max(1, Math.min(configPage - 2, total - 4));
                      const n = start + i;
                      return n <= total ? (
                        <button key={n} onClick={() => setConfigPage(n)}
                          className={`px-2 py-1 rounded text-xs font-medium ${
                            configPage === n ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-700'
                          }`}>{n}</button>
                      ) : null;
                    })}
                    <button onClick={() => setConfigPage(p => Math.min(Math.ceil(filteredConfigs.length / CONFIG_PAGE_SIZE), p + 1))}
                      disabled={configPage === Math.ceil(filteredConfigs.length / CONFIG_PAGE_SIZE)}
                      className="px-2 py-1 rounded text-xs text-slate-400 hover:bg-slate-700 disabled:text-slate-600 disabled:cursor-not-allowed">›</button>
                    <button onClick={() => setConfigPage(Math.ceil(filteredConfigs.length / CONFIG_PAGE_SIZE))}
                      disabled={configPage === Math.ceil(filteredConfigs.length / CONFIG_PAGE_SIZE)}
                      className="px-2 py-1 rounded text-xs text-slate-400 hover:bg-slate-700 disabled:text-slate-600 disabled:cursor-not-allowed">»</button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </RBACGuard>
  );
}

