'use client';

import { useEffect, useState } from 'react';
import { socketIOService } from '@/services/socketIOService';

interface StatusIndicatorProps {
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export default function ConnectivityStatusIndicator({
  showLabel = true,
  size = 'md',
  className = ''
}: StatusIndicatorProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [mqttStatus, setMqttStatus] = useState<'online' | 'offline'>('offline');
  const [internetConnected, setInternetConnected] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    setIsConnected(socketIOService.isConnected());

    socketIOService.on('connected', () => {
      setIsConnected(true);
      setLastUpdate(new Date());
    });

    socketIOService.on('disconnected', () => {
      setIsConnected(false);
      setLastUpdate(new Date());
    });

    socketIOService.on('mqtt_status', (data: any) => {
      setMqttStatus(data.status === 'online' ? 'online' : 'offline');
      setLastUpdate(new Date());
    });

    // Desktop emits this when internet drops/restores
    socketIOService.on('internet_status', (data: any) => {
      setInternetConnected(data.connected === true);
      setLastUpdate(new Date());
    });

    const heartbeatInterval = setInterval(() => {
      if (socketIOService.isConnected()) {
        socketIOService.ping().then((latency) => {
          if (latency > 0) setIsConnected(true);
        });
      }
    }, 5000);

    return () => {
      clearInterval(heartbeatInterval);
      socketIOService.off('connected');
      socketIOService.off('disconnected');
      socketIOService.off('mqtt_status');
      socketIOService.off('internet_status');
    };
  }, []);

  const sizeClasses = { sm: 'w-2 h-2', md: 'w-3 h-3', lg: 'w-4 h-4' };
  const labelSizeClasses = { sm: 'text-xs', md: 'text-sm', lg: 'text-base' };

  const isOnline = isConnected && mqttStatus === 'online' && internetConnected;
  const statusColor = isOnline ? 'bg-green-500' : 'bg-red-500';
  const statusText = isOnline ? 'Connected' : 'Disconnected';
  const statusTextColor = isOnline ? 'text-green-400' : 'text-red-400';

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="relative">
        <div className={`${sizeClasses[size]} ${statusColor} rounded-full animate-pulse`} />
        <div className={`${sizeClasses[size]} ${statusColor} rounded-full absolute inset-0 opacity-30 animate-ping`} />
      </div>

      {showLabel && (
        <div className="flex flex-col">
          <span className={`${labelSizeClasses[size]} font-semibold ${statusTextColor}`}>
            {statusText}
          </span>
          {lastUpdate && (
            <span className="text-xs text-slate-500">
              {lastUpdate.toLocaleTimeString()}
            </span>
          )}
        </div>
      )}

      <div className="group relative">
        <div className="hidden group-hover:block absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-slate-800 text-white text-xs rounded-lg whitespace-nowrap z-50">
          <div>Socket.IO: {isConnected ? '✓ Connected' : '✗ Disconnected'}</div>
          <div>MQTT: {mqttStatus === 'online' ? '✓ Online' : '✗ Offline'}</div>
          <div>Internet: {internetConnected ? '✓ Online' : '✗ Offline'}</div>
          {lastUpdate && <div>Last Update: {lastUpdate.toLocaleTimeString()}</div>}
        </div>
      </div>
    </div>
  );
}
