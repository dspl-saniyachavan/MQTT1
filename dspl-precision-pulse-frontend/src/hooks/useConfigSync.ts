import { useEffect, useCallback } from 'react';
import { useSocketIO } from './useSocketIO';
import { configService } from '@/services/configService';

interface ConfigUpdate {
  action: 'created' | 'updated' | 'deleted' | 'bulk_update';
  key?: string;
  value?: string;
  configs?: Array<{ key: string; value: string }>;
  version?: number;
  timestamp?: string;
}

export function useConfigSync(onConfigChange?: (update: ConfigUpdate) => void) {
  const { socket } = useSocketIO();

  useEffect(() => {
    if (!socket) {
      console.log('[CONFIG_SYNC] Socket.IO not connected');
      return;
    }

    const handleConfigUpdate = (data: ConfigUpdate) => {
      console.log('[CONFIG_SYNC] Config update received:', data);
      if (onConfigChange) {
        onConfigChange(data);
      }
    };

    const handleConfigBulkUpdate = (data: ConfigUpdate) => {
      console.log('[CONFIG_SYNC] Bulk config update received:', data);
      if (onConfigChange) {
        onConfigChange(data);
      }
    };

    console.log('[CONFIG_SYNC] Registering Socket.IO config listeners');
    socket.on('config_update', handleConfigUpdate);
    socket.on('config_bulk_update', handleConfigBulkUpdate);

    return () => {
      console.log('[CONFIG_SYNC] Unregistering Socket.IO config listeners');
      socket.off('config_update', handleConfigUpdate);
      socket.off('config_bulk_update', handleConfigBulkUpdate);
    };
  }, [socket, onConfigChange]);

  const refreshConfigs = useCallback(async () => {
    try {
      const response = await configService.getAllConfigs();
      console.log('[CONFIG_SYNC] Configs refreshed:', response);
      return response;
    } catch (err) {
      console.error('[CONFIG_SYNC] Error refreshing configs:', err);
      throw err;
    }
  }, []);

  return { refreshConfigs };
}
