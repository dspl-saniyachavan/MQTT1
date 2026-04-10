// Audit Log Service for tracking telemetry, commands, and user changes

export interface AuditLogEntry {
  event_type: 'TELEMETRY_UPDATE' | 'COMMAND_EXECUTED' | 'USER_CREATED' | 'USER_UPDATED' | 'USER_DELETED' | 'PARAMETER_CHANGED' | 'CONFIG_CHANGED' | 'LOGIN' | 'LOGOUT';
  resource_type: 'telemetry' | 'command' | 'user' | 'parameter' | 'config' | 'auth';
  resource_id: string;
  resource_name: string;
  action: string;
  description: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  old_values?: Record<string, any>;
  new_values?: Record<string, any>;
  metadata?: Record<string, any>;
}

class AuditLogService {
  private backendUrl: string;

  constructor() {
    this.backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
  }

  private getToken(): string {
    return localStorage.getItem('token') || '';
  }

  /**
   * Log telemetry update
   */
  async logTelemetryUpdate(
    parameterId: number,
    parameterName: string,
    oldValue: number,
    newValue: number,
    unit: string
  ): Promise<void> {
    try {
      await this.createAuditLog({
        event_type: 'TELEMETRY_UPDATE',
        resource_type: 'telemetry',
        resource_id: parameterId.toString(),
        resource_name: parameterName,
        action: 'UPDATE',
        description: `Parameter "${parameterName}" updated from ${oldValue} to ${newValue} ${unit}`,
        severity: 'info',
        old_values: { value: oldValue, unit },
        new_values: { value: newValue, unit },
        metadata: { parameter_id: parameterId, unit }
      });
    } catch (error) {
      console.error('[AUDIT] Error logging telemetry update:', error);
    }
  }

  /**
   * Log command execution
   */
  async logCommandExecution(
    commandId: string,
    commandName: string,
    status: 'success' | 'failure',
    result?: string,
    error?: string
  ): Promise<void> {
    try {
      await this.createAuditLog({
        event_type: 'COMMAND_EXECUTED',
        resource_type: 'command',
        resource_id: commandId,
        resource_name: commandName,
        action: 'EXECUTE',
        description: `Command "${commandName}" executed with status: ${status}${error ? ` - ${error}` : ''}`,
        severity: status === 'failure' ? 'error' : 'info',
        new_values: { status, result, error },
        metadata: { command_id: commandId, status }
      });
    } catch (error) {
      console.error('[AUDIT] Error logging command execution:', error);
    }
  }

  /**
   * Log user creation
   */
  async logUserCreated(
    userId: number,
    email: string,
    name: string,
    role: string
  ): Promise<void> {
    try {
      await this.createAuditLog({
        event_type: 'USER_CREATED',
        resource_type: 'user',
        resource_id: userId.toString(),
        resource_name: email,
        action: 'CREATE',
        description: `User "${email}" (${name}) created with role: ${role}`,
        severity: 'warning',
        new_values: { email, name, role, user_id: userId },
        metadata: { user_id: userId, email, role }
      });
    } catch (error) {
      console.error('[AUDIT] Error logging user creation:', error);
    }
  }

  /**
   * Log user update
   */
  async logUserUpdated(
    userId: number,
    email: string,
    changes: Record<string, any>
  ): Promise<void> {
    try {
      const changeDescription = Object.entries(changes)
        .map(([key, value]) => `${key}: ${value}`)
        .join(', ');

      await this.createAuditLog({
        event_type: 'USER_UPDATED',
        resource_type: 'user',
        resource_id: userId.toString(),
        resource_name: email,
        action: 'UPDATE',
        description: `User "${email}" updated: ${changeDescription}`,
        severity: 'warning',
        new_values: changes,
        metadata: { user_id: userId, email, changes }
      });
    } catch (error) {
      console.error('[AUDIT] Error logging user update:', error);
    }
  }

  /**
   * Log user deletion
   */
  async logUserDeleted(
    userId: number,
    email: string,
    name: string
  ): Promise<void> {
    try {
      await this.createAuditLog({
        event_type: 'USER_DELETED',
        resource_type: 'user',
        resource_id: userId.toString(),
        resource_name: email,
        action: 'DELETE',
        description: `User "${email}" (${name}) deleted`,
        severity: 'critical',
        old_values: { email, name, user_id: userId },
        metadata: { user_id: userId, email }
      });
    } catch (error) {
      console.error('[AUDIT] Error logging user deletion:', error);
    }
  }

  /**
   * Log parameter change
   */
  async logParameterChanged(
    parameterId: number,
    parameterName: string,
    oldConfig: Record<string, any>,
    newConfig: Record<string, any>
  ): Promise<void> {
    try {
      const changes = Object.keys(newConfig)
        .filter(key => oldConfig[key] !== newConfig[key])
        .map(key => `${key}: ${oldConfig[key]} → ${newConfig[key]}`)
        .join(', ');

      await this.createAuditLog({
        event_type: 'PARAMETER_CHANGED',
        resource_type: 'parameter',
        resource_id: parameterId.toString(),
        resource_name: parameterName,
        action: 'UPDATE',
        description: `Parameter "${parameterName}" configuration changed: ${changes}`,
        severity: 'warning',
        old_values: oldConfig,
        new_values: newConfig,
        metadata: { parameter_id: parameterId }
      });
    } catch (error) {
      console.error('[AUDIT] Error logging parameter change:', error);
    }
  }

  /**
   * Log configuration change
   */
  async logConfigChanged(
    configKey: string,
    oldValue: any,
    newValue: any
  ): Promise<void> {
    try {
      await this.createAuditLog({
        event_type: 'CONFIG_CHANGED',
        resource_type: 'config',
        resource_id: configKey,
        resource_name: configKey,
        action: 'UPDATE',
        description: `Configuration "${configKey}" changed from "${oldValue}" to "${newValue}"`,
        severity: 'warning',
        old_values: { [configKey]: oldValue },
        new_values: { [configKey]: newValue },
        metadata: { config_key: configKey }
      });
    } catch (error) {
      console.error('[AUDIT] Error logging config change:', error);
    }
  }

  /**
   * Log user login
   */
  async logLogin(email: string, ipAddress?: string): Promise<void> {
    try {
      await this.createAuditLog({
        event_type: 'LOGIN',
        resource_type: 'auth',
        resource_id: email,
        resource_name: email,
        action: 'LOGIN',
        description: `User "${email}" logged in${ipAddress ? ` from ${ipAddress}` : ''}`,
        severity: 'info',
        metadata: { email, ip_address: ipAddress }
      });
    } catch (error) {
      console.error('[AUDIT] Error logging login:', error);
    }
  }

  /**
   * Log user logout
   */
  async logLogout(email: string): Promise<void> {
    try {
      await this.createAuditLog({
        event_type: 'LOGOUT',
        resource_type: 'auth',
        resource_id: email,
        resource_name: email,
        action: 'LOGOUT',
        description: `User "${email}" logged out`,
        severity: 'info',
        metadata: { email }
      });
    } catch (error) {
      console.error('[AUDIT] Error logging logout:', error);
    }
  }

  /**
   * Create audit log entry
   */
  private async createAuditLog(entry: AuditLogEntry): Promise<void> {
    try {
      const token = this.getToken();
      if (!token) {
        console.warn('[AUDIT] No token available for audit logging');
        return;
      }

      const response = await fetch(`${this.backendUrl}/api/audit/logs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        credentials: 'include',
        body: JSON.stringify(entry)
      });

      if (!response.ok) {
        console.error('[AUDIT] Failed to create audit log:', response.status);
      }
    } catch (error) {
      console.error('[AUDIT] Error creating audit log:', error);
    }
  }

  /**
   * Get audit logs with filters
   */
  async getAuditLogs(
    filters?: {
      event_type?: string;
      resource_type?: string;
      actor_email?: string;
      severity?: string;
      status?: string;
      start_date?: string;
      end_date?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<{ logs: any[]; total_count: number }> {
    try {
      const token = this.getToken();
      const params = new URLSearchParams();

      if (filters) {
        Object.entries(filters).forEach(([key, value]) => {
          if (value !== undefined && value !== null && value !== '') {
            params.append(key, String(value));
          }
        });
      }

      const response = await fetch(`${this.backendUrl}/api/audit/logs?${params}`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch audit logs: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('[AUDIT] Error fetching audit logs:', error);
      throw error;
    }
  }

  /**
   * Get audit statistics
   */
  async getAuditStatistics(days: number = 7): Promise<any> {
    try {
      const token = this.getToken();
      const response = await fetch(`${this.backendUrl}/api/audit/statistics?days=${days}`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch audit statistics: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('[AUDIT] Error fetching audit statistics:', error);
      throw error;
    }
  }

  /**
   * Export audit logs as CSV
   */
  async exportAuditLogs(filters?: Record<string, any>): Promise<Blob> {
    try {
      const token = this.getToken();
      const params = new URLSearchParams();

      if (filters) {
        Object.entries(filters).forEach(([key, value]) => {
          if (value !== undefined && value !== null && value !== '') {
            params.append(key, String(value));
          }
        });
      }

      const response = await fetch(`${this.backendUrl}/api/audit/export?${params}`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error(`Failed to export audit logs: ${response.status}`);
      }

      return await response.blob();
    } catch (error) {
      console.error('[AUDIT] Error exporting audit logs:', error);
      throw error;
    }
  }
}

export const auditLogService = new AuditLogService();
