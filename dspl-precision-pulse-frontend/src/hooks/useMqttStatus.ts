import { useEffect, useRef, useState, useCallback } from 'react';
import { socketIOService } from '@/services/socketIOService';

export type MqttConnectionState = 'online' | 'offline' | 'reconnecting';

export interface SyncStatus {
  status: 'idle' | 'reconnected' | 'disconnected' | 'synced' | 'failed';
  total?: number;
  synced?: number;
  unsynced?: number;
  flushed?: number;
  error?: string;
  lastUpdate: number;
}

interface MqttStatusData {
  state: MqttConnectionState;
  lastUpdate: number;
  lastError?: string;
  brokerConnected: boolean;   // backend ↔ MQTT broker
  desktopConnected: boolean;  // desktop ↔ MQTT broker (heartbeat-based)
}

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
// Desktop is considered offline if no heartbeat received in this window
const DESKTOP_HEARTBEAT_TIMEOUT_MS = 15000;

export function useMqttStatus() {
  const [state, setState]           = useState<MqttConnectionState>('offline');
  const [statusData, setStatusData] = useState<MqttStatusData>({
    state: 'offline', lastUpdate: Date.now(),
    brokerConnected: false, desktopConnected: false,
  });
  const [syncStatus, setSyncStatus] = useState<SyncStatus>({ status: 'idle', lastUpdate: Date.now() });
  const [isLoading, setIsLoading]   = useState(true);

  const stateRef            = useRef<MqttConnectionState>('offline');
  const brokerConnectedRef  = useRef(false);
  const desktopConnectedRef = useRef(false);
  const lastHeartbeatRef    = useRef<number>(0);

  // Derive combined state: online only if broker AND desktop are both connected
  const recompute = useCallback(() => {
    const broker  = brokerConnectedRef.current;
    const desktop = desktopConnectedRef.current;
    const combined: MqttConnectionState = (broker && desktop) ? 'online'
      : broker ? 'reconnecting'   // broker up but desktop not seen yet
      : 'offline';
    stateRef.current = combined;
    setState(combined);
    setStatusData({
      state: combined,
      lastUpdate: Date.now(),
      brokerConnected: broker,
      desktopConnected: desktop,
    });
  }, []);

  const setBroker  = useCallback((on: boolean) => { brokerConnectedRef.current = on;  recompute(); }, [recompute]);
  const setDesktop = useCallback((on: boolean) => { desktopConnectedRef.current = on; recompute(); }, [recompute]);

  // ── Poll backend /api/mqtt/status every 10 s ──────────────────────────────
  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch(`${BACKEND}/api/mqtt/status`);
        const data = r.ok ? await r.json() : null;
        setBroker(!!(data?.status === 'online' || data?.connected === true));
      } catch { setBroker(false); }
    };
    poll().finally(() => setIsLoading(false));
    const id = setInterval(poll, 10000);
    return () => clearInterval(id);
  }, [setBroker]);

  // ── Heartbeat timeout — mark desktop offline if no heartbeat for 15 s ────
  useEffect(() => {
    const id = setInterval(() => {
      const age = Date.now() - lastHeartbeatRef.current;
      const wasConnected = desktopConnectedRef.current;
      if (age > DESKTOP_HEARTBEAT_TIMEOUT_MS && wasConnected) {
        setDesktop(false);
      }
    }, 5000);
    return () => clearInterval(id);
  }, [setDesktop]);

  // ── Socket.IO listeners ───────────────────────────────────────────────────
  useEffect(() => {
    socketIOService.connectIfNeeded();

    const handleMqttStatus = (data: any) => {
      setBroker(!!(data?.status === 'online' || data?.connected === true));
    };
    const handleMqttConnected    = () => setBroker(true);
    const handleMqttDisconnected = (d: any) => {
      setBroker(false);
      setSyncStatus(prev => ({ ...prev, status: 'disconnected', lastUpdate: Date.now() }));
    };

    // Telemetry / heartbeat from desktop → desktop is alive
    const handleTelemetry = () => {
      lastHeartbeatRef.current = Date.now();
      if (!desktopConnectedRef.current) setDesktop(true);
    };

    const handleSyncStatus = (data: any) => {
      setSyncStatus({
        status: data.status ?? 'idle', total: data.total, synced: data.synced,
        unsynced: data.unsynced, flushed: data.flushed, error: data.error,
        lastUpdate: Date.now(),
      });
      if (data.status === 'reconnected' || data.status === 'synced') setBroker(true);
    };

    socketIOService.on('mqtt_status',          handleMqttStatus);
    socketIOService.on('mqtt_connected',       handleMqttConnected);
    socketIOService.on('mqtt_disconnected',    handleMqttDisconnected);
    socketIOService.on('telemetry',            handleTelemetry);
    socketIOService.on('parameter_stream_update', handleTelemetry);
    socketIOService.on('sync_status',          handleSyncStatus);

    return () => {
      socketIOService.off('mqtt_status',          handleMqttStatus);
      socketIOService.off('mqtt_connected',       handleMqttConnected);
      socketIOService.off('mqtt_disconnected',    handleMqttDisconnected);
      socketIOService.off('telemetry',            handleTelemetry);
      socketIOService.off('parameter_stream_update', handleTelemetry);
      socketIOService.off('sync_status',          handleSyncStatus);
    };
  }, [setBroker, setDesktop]);

  const getStatusLabel = useCallback(() => {
    if (state === 'online')       return 'Desktop + Broker Online';
    if (state === 'reconnecting') return 'Broker Up · Desktop Offline';
    return 'MQTT Offline';
  }, [state]);

  const getStatusColor = useCallback(() => {
    if (state === 'online') return {
      bg: 'bg-emerald-500/10', border: 'border-emerald-500/30',
      text: 'text-emerald-400', dot: 'bg-emerald-500',
    };
    if (state === 'reconnecting') return {
      bg: 'bg-amber-500/10', border: 'border-amber-500/30',
      text: 'text-amber-400', dot: 'bg-amber-500',
    };
    return {
      bg: 'bg-red-500/10', border: 'border-red-500/30',
      text: 'text-red-400', dot: 'bg-red-500',
    };
  }, [state]);

  return {
    mqttStatus:      state === 'online' ? 'online' : 'offline' as 'online' | 'offline',
    connectionState: state,
    statusData,
    syncStatus,
    isLoading,
    isConnected:     state === 'online',
    isReconnecting:  state === 'reconnecting',
    getStatusLabel,
    getStatusColor,
  };
}
