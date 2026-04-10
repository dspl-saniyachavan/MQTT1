import { useEffect, useState, useCallback, use } from 'react';
import io, { Socket } from 'socket.io-client';

interface UseSocketIOOptions {
  url?: string;
  autoConnect?: boolean;
}

export function useSocketIO(options: UseSocketIOOptions = {}) {
  const { url = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000', autoConnect = true } = options;
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [telemetryData, setTelemetryData] = useState<any>(null);
  const [mqttStatus, setMqttStatus] = useState<'online' | 'offline'>('offline');

  useEffect(() => {
    if (!autoConnect) return;

    console.log('[Socket.IO] Initializing connection to', url);
    const newSocket = io(url, {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 10,
      timeout: 20000,
      // polling only — Werkzeug dev server does not support WebSocket upgrade
      transports: ['polling'],
      upgrade: false,
      path: '/socket.io',
      withCredentials: true
    });

    newSocket.on('connect', () => {
      setIsConnected(true);
      console.log('[Socket.IO] Connected, SID:', newSocket.id);
    });

    newSocket.on('disconnect', (reason) => {
      setIsConnected(false);
      console.log('[Socket.IO] Disconnected, reason:', reason);
      
      if (reason === 'io server disconnect') {
        console.log('[Socket.IO] Server initiated disconnect, reconnecting...');
        setTimeout(() => {
          if (!newSocket.connected) {
            newSocket.connect();
          }
        }, 1000);
      } else if (reason === 'transport close' || reason === 'transport error') {
        console.log('[Socket.IO] Transport issue, auto-reconnect will handle it');
      } else {
        console.log('[Socket.IO] Disconnect reason:', reason, '- auto-reconnect active');
      }
    });

    newSocket.on('connect_error', (error) => {
      console.warn('[Socket.IO] Connection error (will retry):', error.message);
      setIsConnected(false);
    });

    newSocket.on('reconnect', (attemptNumber) => {
      console.log('[Socket.IO] Reconnected after', attemptNumber, 'attempts');
      setIsConnected(true);
    });

    newSocket.on('reconnect_attempt', (attemptNumber) => {
      console.log('[Socket.IO] Reconnection attempt', attemptNumber);
    });

    newSocket.on('reconnect_error', (error) => {
      console.error('[Socket.IO] Reconnection error:', error.message);
    });

    newSocket.on('reconnect_failed', () => {
      console.error('[Socket.IO] Reconnection failed after all attempts');
      console.log('[Socket.IO] Will continue attempting to reconnect in background');
    });

    newSocket.on('connection_response', (data) => {
      console.log('[Socket.IO] Connection response:', data);
    });

    newSocket.on('telemetry_update', (data) => {
      console.log('[Socket.IO] Telemetry update received');
      setTelemetryData(data);
    });

    newSocket.on('mqtt_status', (data: { status: 'online' | 'offline' }) => {
      console.log('[Socket.IO] MQTT status event received:', data.status);
      setMqttStatus(data.status);
    });

    newSocket.on('error', (error) => {
      console.error('[Socket.IO] Error:', error);
    });

    setSocket(newSocket);

    return () => {
      console.log('[Socket.IO] Cleaning up connection');
      if (newSocket) {
        newSocket.disconnect();
      }
    };
  }, [url, autoConnect]);

  const authenticate = useCallback((userId: string) => {
    if (socket) {
      console.log('[Socket.IO] Authenticating user:', userId);
      socket.emit('authenticate', { user_id: userId });
    }
  }, [socket]);

  return {
    socket,
    isConnected,
    telemetryData,
    mqttStatus,
    authenticate,
    url
  };
}
