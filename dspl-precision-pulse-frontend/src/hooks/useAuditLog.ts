import { useCallback } from 'react';
import { auditLogService } from '@/services/auditLogService';

export function useAuditLog() {
  const logTelemetryUpdate = useCallback(
    async (parameterId: number, parameterName: string, oldValue: number, newValue: number, unit: string) => {
      await auditLogService.logTelemetryUpdate(parameterId, parameterName, oldValue, newValue, unit);
    },
    []
  );

  const logCommandExecution = useCallback(
    async (commandId: string, commandName: string, status: 'success' | 'failure', result?: string, error?: string) => {
      await auditLogService.logCommandExecution(commandId, commandName, status, result, error);
    },
    []
  );

  const logUserCreated = useCallback(
    async (userId: number, email: string, name: string, role: string) => {
      await auditLogService.logUserCreated(userId, email, name, role);
    },
    []
  );

  const logUserUpdated = useCallback(
    async (userId: number, email: string, changes: Record<string, any>) => {
      await auditLogService.logUserUpdated(userId, email, changes);
    },
    []
  );

  const logUserDeleted = useCallback(
    async (userId: number, email: string, name: string) => {
      await auditLogService.logUserDeleted(userId, email, name);
    },
    []
  );

  const logParameterChanged = useCallback(
    async (parameterId: number, parameterName: string, oldConfig: Record<string, any>, newConfig: Record<string, any>) => {
      await auditLogService.logParameterChanged(parameterId, parameterName, oldConfig, newConfig);
    },
    []
  );

  const logConfigChanged = useCallback(
    async (configKey: string, oldValue: any, newValue: any) => {
      await auditLogService.logConfigChanged(configKey, oldValue, newValue);
    },
    []
  );

  const logLogin = useCallback(
    async (email: string, ipAddress?: string) => {
      await auditLogService.logLogin(email, ipAddress);
    },
    []
  );

  const logLogout = useCallback(
    async (email: string) => {
      await auditLogService.logLogout(email);
    },
    []
  );

  return {
    logTelemetryUpdate,
    logCommandExecution,
    logUserCreated,
    logUserUpdated,
    logUserDeleted,
    logParameterChanged,
    logConfigChanged,
    logLogin,
    logLogout
  };
}
