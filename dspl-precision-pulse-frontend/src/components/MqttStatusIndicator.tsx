'use client';

import React, { useState } from 'react';
import { useMqttStatus } from '@/hooks/useMqttStatus';

interface MqttStatusIndicatorProps {
  showLabel?:   boolean;
  showTooltip?: boolean;
  size?:        'sm' | 'md' | 'lg';
  className?:   string;
}

export default function MqttStatusIndicator({
  showLabel   = true,
  showTooltip = true,
  size        = 'md',
  className   = '',
}: MqttStatusIndicatorProps) {
  const {
    connectionState,
    statusData,
    syncStatus,
    isLoading,
    getStatusLabel,
    getStatusColor,
  } = useMqttStatus();

  const [showDetails, setShowDetails] = useState(false);
  const colors = getStatusColor();

  const sizeClasses    = { sm: 'px-2 py-1 text-xs', md: 'px-3 sm:px-4 py-2 text-sm', lg: 'px-4 py-3 text-base' };
  const dotSizeClasses = { sm: 'w-1.5 h-1.5',       md: 'w-2 h-2',                   lg: 'w-3 h-3' };

  const isReconnecting = connectionState === 'reconnecting';
  const isOnline       = connectionState === 'online';
  const hasSyncFailed  = syncStatus.status === 'failed';
  const hasPendingSync = (syncStatus.unsynced ?? 0) > 0;

  const lastUpdateTime = new Date(statusData.lastUpdate).toLocaleTimeString();

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setShowDetails(!showDetails)}
        className={`flex items-center gap-2 rounded-lg border font-semibold transition-all duration-300
          ${sizeClasses[size]} ${colors.bg} ${colors.border} ${colors.text}
          hover:opacity-80 cursor-pointer`}
        title={showTooltip ? `MQTT: ${getStatusLabel()}` : undefined}
        disabled={isLoading}
      >
        {/* Dot */}
        <div className={`relative ${dotSizeClasses[size]} rounded-full ${colors.dot}`}>
          {isOnline && (
            <div className={`absolute inset-0 rounded-full ${colors.dot} animate-ping opacity-75`} />
          )}
          {isReconnecting && (
            <div className={`absolute inset-0 rounded-full ${colors.dot} animate-pulse`} />
          )}
        </div>

        {showLabel && (
          <span className="font-semibold whitespace-nowrap">
            {isLoading ? 'Loading…' : getStatusLabel()}
          </span>
        )}

        {/* Failed-sync badge */}
        {hasSyncFailed && (
          <span className="ml-1 px-1.5 py-0.5 bg-red-600 text-white text-xs rounded-full font-bold">
            SYNC FAILED
          </span>
        )}

        {/* Pending-sync badge */}
        {!hasSyncFailed && hasPendingSync && (
          <span className="ml-1 px-1.5 py-0.5 bg-amber-600 text-white text-xs rounded-full font-bold">
            {syncStatus.unsynced} pending
          </span>
        )}
      </button>

      {/* Details popup */}
      {showDetails && showTooltip && (
        <div className={`absolute top-full mt-2 right-0 z-50 bg-slate-900 border-2 rounded-lg p-3 shadow-xl min-w-[220px] ${colors.border}`}>
          <button
            onClick={() => setShowDetails(false)}
            className="absolute top-1 right-2 text-slate-400 hover:text-slate-200 text-lg leading-none"
          >×</button>

          <div className="space-y-2">
            {/* State row */}
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${colors.dot}`} />
              <span className={`font-semibold ${colors.text}`}>{getStatusLabel()}</span>
            </div>

            <div className="text-xs text-slate-400 space-y-1 border-t border-slate-700 pt-2">
              <div>Last update: {lastUpdateTime}</div>

              {/* Sync status section */}
              {syncStatus.status !== 'idle' && (
                <div className="mt-1 space-y-0.5">
                  <div className="font-semibold text-slate-300">Sync status</div>

                  {syncStatus.status === 'disconnected' && (
                    <div className="text-amber-400">⚠ Buffering offline data</div>
                  )}
                  {syncStatus.status === 'reconnected' && (
                    <div className="text-amber-300">
                      ↻ Reconnected — flushing {syncStatus.unsynced ?? 0} records
                    </div>
                  )}
                  {syncStatus.status === 'synced' && (
                    <div className="text-emerald-400">
                      ✓ Synced {syncStatus.flushed ?? 0} buffered records
                    </div>
                  )}
                  {syncStatus.status === 'failed' && (
                    <div className="text-red-400">
                      ✗ Sync failed: {syncStatus.error ?? 'unknown error'}
                    </div>
                  )}

                  {syncStatus.total !== undefined && (
                    <div>PostgreSQL total: {syncStatus.total}</div>
                  )}
                  {syncStatus.unsynced !== undefined && syncStatus.unsynced > 0 && (
                    <div className="text-amber-400">Unsynced: {syncStatus.unsynced}</div>
                  )}
                </div>
              )}

              {statusData.lastError && (
                <div className="text-red-400 mt-1">Error: {statusData.lastError}</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
