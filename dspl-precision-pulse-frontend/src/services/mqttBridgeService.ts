/**
 * mqttBridgeService — all create/update/delete operations go through
 * POST /api/mqtt-bridge/publish instead of hitting REST routes directly.
 *
 * The backend bridge publishes to MQTT; the subscriber writes to PostgreSQL
 * and emits the result back via Socket.IO.  Read-only GETs still use REST.
 */

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

function getToken(): string {
  return typeof window !== 'undefined' ? (localStorage.getItem('token') || '') : '';
}

async function publish(topic: string, payload: Record<string, unknown>): Promise<{ ok: boolean; msg_id?: string; error?: string }> {
  try {
    const res = await fetch(`${BACKEND}/api/mqtt-bridge/publish`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`,
      },
      body: JSON.stringify({ topic, payload }),
    });
    const data = await res.json();
    if (!res.ok) return { ok: false, error: data.error || `HTTP ${res.status}` };
    return { ok: true, msg_id: data.msg_id };
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

// ── Parameters ────────────────────────────────────────────────────────────────

export const mqttParameters = {
  create: (param: { name: string; unit: string; description: string; enabled?: boolean }) =>
    publish('precisionpulse/sync/parameters', {
      type: 'parameter_created', action: 'create', parameter: param,
    }),

  update: (id: number, changes: Record<string, unknown>) =>
    publish('precisionpulse/sync/parameters', {
      type: 'parameter_updated', action: 'update', parameter: { id, ...changes },
    }),

  delete: (id: number) =>
    publish('precisionpulse/sync/parameters', {
      type: 'parameter_deleted', action: 'delete', parameter: { id },
    }),

  setAlertRange: (id: number, alert_min: number | null, alert_max: number | null, warn_min: number | null, warn_max: number | null) =>
    publish('precisionpulse/sync/parameters', {
      type: 'parameter_updated', action: 'update',
      parameter: { id, alert_min, alert_max, warn_min, warn_max },
    }),

  setValue: (parameterId: number, value: number) =>
    publish('precisionpulse/desktop/parameter/edit', {
      type: 'parameter_value_updated', parameter_id: parameterId, value,
      timestamp: new Date().toISOString(),
    }),
};

// ── Users ─────────────────────────────────────────────────────────────────────

export const mqttUsers = {
  create: (user: { email: string; name: string; password_hash: string; role: string; is_active?: boolean }) =>
    publish('precisionpulse/sync/users/created', { type: 'user_created', user }),

  update: (user: { id?: number; email: string; name?: string; role?: string; is_active?: boolean; avatar_url?: string | null }) =>
    publish('precisionpulse/sync/users/updated', { type: 'user_updated', user }),

  delete: (user: { id?: number; email: string }) =>
    publish('precisionpulse/sync/users/deleted', { type: 'user_deleted', user }),

  changeRole: (userId: number, email: string, oldRole: string, newRole: string) =>
    publish('precisionpulse/sync/roles/changed', {
      type: 'role_changed', user_id: userId, email, old_role: oldRole, new_role: newRole,
    }),
};

// ── Config ────────────────────────────────────────────────────────────────────

export const mqttConfig = {
  update: (key: string, value: string) =>
    publish('precisionpulse/config/update', { type: 'config_updated', key, value }),

  bulkUpdate: (configs: Array<{ key: string; value: string }>) =>
    publish('precisionpulse/config/bulk-update', { type: 'config_bulk_updated', configs }),
};
