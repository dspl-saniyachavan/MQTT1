'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { socketIOService } from '@/services/socketIOService';

interface CommandResult {
  success: boolean;
  command_id?: string;
  message?: string;
  error?: string;
}

interface CommandAck {
  command_id: string;
  device_id: string;
  ack_type: string;
  status: string;
  message?: string;
}

const API = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

export default function CommandsPage() {
  const router = useRouter();
  const [token, setToken] = useState('');
  const [loading, setLoading] = useState<string | null>(null);
  const [results, setResults] = useState<{ id: string; cmd: string; result: CommandResult; ts: string }[]>([]);
  const [acks, setAcks] = useState<CommandAck[]>([]);
  const [configKey, setConfigKey] = useState('TELEMETRY_FETCH_INTERVAL_MS');
  const [configValue, setConfigValue] = useState('3000');

  useEffect(() => {
    const t = localStorage.getItem('token');
    const u = localStorage.getItem('user');
    if (!t) { router.push('/login'); return; }
    const user = u ? JSON.parse(u) : {};
    if (user.role !== 'admin') { router.push('/dashboard'); return; }
    setToken(t);

    socketIOService.connectIfNeeded();
    const handleAck = (data: CommandAck) => {
      setAcks(prev => [data, ...prev].slice(0, 20));
    };
    socketIOService.on('command_ack', handleAck);
    return () => socketIOService.off('command_ack', handleAck);
  }, [router]);

  const sendCommand = useCallback(async (endpoint: string, body: object, label: string) => {
    setLoading(label);
    try {
      const res = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data: CommandResult = await res.json();
      setResults(prev => [{ id: data.command_id || Date.now().toString(), cmd: label, result: data, ts: new Date().toLocaleTimeString() }, ...prev].slice(0, 10));
    } catch (e: any) {
      setResults(prev => [{ id: Date.now().toString(), cmd: label, result: { success: false, error: e.message }, ts: new Date().toLocaleTimeString() }, ...prev].slice(0, 10));
    } finally {
      setLoading(null);
    }
  }, [token]);

  const forceSync    = () => sendCommand('/api/remote-commands/force-sync',   { sync_type: 'full' }, 'Force Sync');
  const restartStream = () => sendCommand('/api/remote-commands/custom',      { command_type: 'restart' }, 'Restart Stream');
  const updateConfig  = () => sendCommand('/api/remote-commands/update-config', { config: { [configKey]: configValue } }, 'Update Config');

  const btnBase = 'px-5 py-2.5 rounded-lg font-semibold text-sm text-white disabled:opacity-50 transition-all';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6 sm:p-10">
      <div className="max-w-3xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Remote Commands</h1>
            <p className="text-slate-400 text-sm mt-1">Send commands to connected desktop devices</p>
          </div>
          <button onClick={() => router.push('/dashboard')} className="text-slate-400 hover:text-white text-sm"> Dashboard</button>
        </div>

        {/* Command Buttons */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-2xl p-6 space-y-6">
          <h2 className="text-slate-300 font-semibold text-sm uppercase tracking-widest">Commands</h2>

          <div className="flex flex-wrap gap-3">
            <button onClick={forceSync} disabled={!!loading}
              className={`${btnBase} bg-blue-600 hover:bg-blue-700`}>
              {loading === 'Force Sync' ? ' Sending...' : ' Force Sync'}
            </button>
            <button onClick={restartStream} disabled={!!loading}
              className={`${btnBase} bg-amber-600 hover:bg-amber-700`}>
              {loading === 'Restart Stream' ? ' Sending...' : ' Restart Stream'}
            </button>
          </div>
        </div>

        {/* Command Results */}
        {results.length > 0 && (
          <div className="bg-slate-800/60 border border-slate-700 rounded-2xl p-6 space-y-3">
            <h2 className="text-slate-300 font-semibold text-sm uppercase tracking-widest">Sent Commands</h2>
            {results.map(r => (
              <div key={r.id} className={`flex items-start justify-between rounded-lg px-4 py-3 text-sm ${r.result.success ? 'bg-emerald-900/30 border border-emerald-700/40' : 'bg-red-900/30 border border-red-700/40'}`}>
                <div>
                  <span className="font-semibold text-white">{r.cmd}</span>
                  <span className="ml-2 text-slate-400 text-xs">{r.ts}</span>
                  {r.result.command_id && <p className="text-slate-500 text-xs mt-0.5">ID: {r.result.command_id}</p>}
                  {r.result.error && <p className="text-red-400 text-xs mt-0.5">{r.result.error}</p>}
                </div>
                <span className={`text-xs font-bold ${r.result.success ? 'text-emerald-400' : 'text-red-400'}`}>
                  {r.result.success ? '✓ Sent' : '✗ Failed'}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* ACK Feed */}
        {acks.length > 0 && (
          <div className="bg-slate-800/60 border border-slate-700 rounded-2xl p-6 space-y-3">
            <h2 className="text-slate-300 font-semibold text-sm uppercase tracking-widest">Acknowledgments (live)</h2>
            {acks.map((a, i) => (
              <div key={i} className="flex items-center justify-between text-sm bg-slate-900/50 rounded-lg px-4 py-2">
                <div>
                  <span className="text-white font-medium">{a.ack_type}</span>
                  <span className="text-slate-400 ml-2 text-xs">from {a.device_id}</span>
                  {a.message && <span className="text-slate-500 ml-2 text-xs">— {a.message}</span>}
                </div>
                <span className={`text-xs font-bold ${a.status === 'success' ? 'text-emerald-400' : 'text-red-400'}`}>{a.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}