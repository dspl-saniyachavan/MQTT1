import io, { Socket } from 'socket.io-client';

const SOCKET_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

class SocketIOService {
  private socket: Socket | null = null;
  private readonly listeners: Map<string, Set<Function>> = new Map();
  private rawHandlers: Record<string, (data: any) => void> = {};
  private builtinEvents: Set<string> = new Set();
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts = 5;
  private readonly reconnectDelay = 1000;

  connect(token?: string): Promise<void> {
    // Reuse existing live socket
    if (this.socket?.connected) {
      return Promise.resolve();
    }
    // Tear down stale socket
    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
    }

    return new Promise((resolve) => {
      try {
        const socketOptions: any = {
          reconnection: true,
          reconnectionDelay: this.reconnectDelay,
          reconnectionDelayMax: 10000,
          reconnectionAttempts: Infinity,
          // polling only — Werkzeug dev server does not support WebSocket upgrade
          transports: ['polling'],
          upgrade: false,
          path: '/socket.io',
          autoConnect: true,
        };

        if (token) {
          socketOptions.auth = { token };
        }

        this.socket = io(SOCKET_URL, socketOptions);

        this.socket.on('connect', () => {
          console.log('[SocketIO] Connected');
          this.reconnectAttempts = 0;
          this.registerEventListeners();
          this.notify('connected', undefined);
          resolve();
        });

        this.socket.on('disconnect', (reason) => {
          console.log('[SocketIO] Disconnected:', reason);
          this.notify('disconnected', { reason });
        });

        this.socket.on('connect_error', (error) => {
          // Do NOT reject — socket.io will keep retrying automatically.
          // Rejecting here would kill the promise and stop connectIfNeeded from working.
          console.warn('[SocketIO] Connection error (will retry):', error.message);
          this.notify('connection_error', error);
        });

        this.socket.on('reconnect', () => {
          console.log('[SocketIO] Reconnected — re-registering listeners');
          this.registerEventListeners();
          this.notify('connected', undefined);
        });

        this.socket.on('reconnect_attempt', (n) => {
          this.reconnectAttempts = n;
          console.log('[SocketIO] Reconnect attempt', n);
        });

      } catch (error) {
        console.error('[SocketIO] Connection failed:', error);
        // Still resolve so callers are not left with an unhandled rejection
        resolve();
      }
    });
  }

  private notify(event: string, data: any) {
    this.listeners.get(event)?.forEach((cb) => {
      try { cb(data); } catch (e) { console.error(`[SocketIO] Listener error on ${event}:`, e); }
    });
  }

  private registerEventListeners() {
    if (!this.socket) return;

    // Remove all previous socket listeners to avoid duplicates on reconnect
    this.socket.removeAllListeners();

    // Re-attach lifecycle listeners lost by removeAllListeners
    this.socket.on('disconnect', (reason) => {
      console.log('[SocketIO] Disconnected:', reason);
      this.notify('disconnected', { reason });
    });
    this.socket.on('reconnect', () => {
      console.log('[SocketIO] Reconnected — re-registering listeners');
      this.registerEventListeners();
    });
    this.socket.on('reconnect_attempt', () => { this.reconnectAttempts++; });
    this.socket.on('reconnect_failed', () => { this.notify('reconnection_failed', undefined); });

    // Builtin server events — fan out through notify()
    const builtins: Record<string, (data: any) => void> = {
      'connection_response': (d) => { console.log('[SocketIO] connection_response:', d); this.notify('connection_response', d); },
      'mqtt_status':         (d) => { console.log('[SocketIO] mqtt_status:', d);         this.notify('mqtt_status', d); },
      'mqtt_connected':      (d) => { this.notify('mqtt_connected', d); },
      'mqtt_disconnected':   (d) => { this.notify('mqtt_disconnected', d); },
      'internet_status':     (d) => { console.log('[SocketIO] internet_status:', d);     this.notify('internet_status', d); },
      'telemetry':           (d) => { this.notify('telemetry', d); },
      'telemetry_update':    (d) => { this.notify('telemetry_update', d); },
      'parameter_stream_update': (d) => { this.notify('parameter_stream_update', d); },
      'parameter_changed':   (d) => { this.notify('parameter_changed', d); },
      'parameter_created':    (d) => { this.notify('parameter_created', d); },
      'parameter_updated':    (d) => { this.notify('parameter_updated', d); },
      'parameter_deleted':    (d) => { this.notify('parameter_deleted', d); },
      'command_executed':    (d) => { this.notify('command_executed', d); },
      'command_ack':         (d) => { this.notify('command_ack', d); },
      'remote_command':      (d) => { this.notify('remote_command', d); },
      'sync_status':         (d) => { console.log('[SocketIO] sync_status:', d);         this.notify('sync_status', d); },
      'stream_restart':      (d) => { this.notify('stream_restart', d); },
      'config_update':       (d) => { this.notify('config_update', d); },
      'config_bulk_update':  (d) => { this.notify('config_bulk_update', d); },
      'user_logged_in':      (d) => { this.notify('user_logged_in', d); },
      'user_logged_out':     (d) => { this.notify('user_logged_out', d); },
      'alert_triggered':     (d) => { this.notify('alert_triggered', d); },
      'parameter_value_updated': (d) => { this.notify('parameter_value_updated', d); },
      'pong':                (d) => { this.notify('pong', d); },
      'error':               (d) => { console.error('[SocketIO] error:', d); this.notify('error', d); },
    };

    Object.entries(builtins).forEach(([event, handler]) => {
      this.socket!.on(event, handler);
    });

    // Dynamic events registered via on() that are NOT already in builtins
    Object.entries(this.rawHandlers).forEach(([event, handler]) => {
      if (!(event in builtins)) {
        this.socket!.on(event, handler);
      }
    });

    // Store builtins map so on() can skip re-registering builtin events
    this.builtinEvents = new Set(Object.keys(builtins));
  }

  disconnect() {
    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
      console.log('[SocketIO] Disconnected');
    }
  }

  isConnected(): boolean {
    return this.socket?.connected || false;
  }

  async connectIfNeeded(): Promise<void> {
    // If socket exists and is connected, nothing to do
    if (this.socket?.connected) return;
    // If socket exists but is disconnected, let socket.io's built-in
    // reconnection handle it — just call connect() to wake it up
    if (this.socket && !this.socket.connected) {
      this.socket.connect();
      return;
    }
    // No socket yet — create one
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    await this.connect(token || undefined);
  }

  emit(event: string, data?: any) {
    if (this.socket?.connected) {
      this.socket.emit(event, data);
    }
  }

  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
      // Only register a raw socket handler for non-builtin events.
      // Builtin events already fan out via notify() inside registerEventListeners().
      if (!this.builtinEvents.has(event)) {
        const rawHandler = (data: any) => { this.notify(event, data); };
        this.rawHandlers[event] = rawHandler;
        if (this.socket) {
          this.socket.on(event, rawHandler);
        }
      }
    }
    this.listeners.get(event)!.add(callback);
  }

  off(event: string, callback?: Function) {
    if (!callback) {
      this.listeners.delete(event);
      const rawHandler = this.rawHandlers[event];
      if (this.socket && rawHandler) {
        this.socket.off(event, rawHandler);
      }
      delete this.rawHandlers[event];
    } else {
      this.listeners.get(event)?.delete(callback);
    }
  }

  once(event: string, callback: Function) {
    const wrapped = (data: any) => {
      callback(data);
      this.off(event, wrapped);
    };
    this.on(event, wrapped);
  }

  ping(): Promise<number> {
    return new Promise((resolve) => {
      if (!this.socket?.connected) { resolve(-1); return; }
      const start = Date.now();
      this.once('pong', () => resolve(Date.now() - start));
      this.emit('ping');
    });
  }

  authenticate(userId: string) { this.emit('authenticate', { user_id: userId }); }
  subscribeToParameter(parameterId: string) { this.emit('subscribe_parameter', { parameter_id: parameterId }); }
  unsubscribeFromParameter(parameterId: string) { this.emit('unsubscribe_parameter', { parameter_id: parameterId }); }
  subscribeToDevice(deviceId: string) { this.emit('subscribe_device', { device_id: deviceId }); }
  unsubscribeFromDevice(deviceId: string) { this.emit('unsubscribe_device', { device_id: deviceId }); }
}

export const socketIOService = new SocketIOService();
