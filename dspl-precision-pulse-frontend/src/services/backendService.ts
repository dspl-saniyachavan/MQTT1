import { apiClient } from '@/lib/api';

// Types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: User;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  role?: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'user' | 'client';
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Parameter {
  id: string;
  name: string;
  unit: string;
  min_value: number;
  max_value: number;
  description?: string;
}

export interface Telemetry {
  id: string;
  parameter_id: string;
  value: number;
  timestamp: string;
  device_id?: string;
}

export interface TelemetryUpdate {
  parameter_id: string;
  value: number;
  unit?: string;
}

export interface AuditLog {
  id: string;
  event_type: string;
  resource_type: string;
  resource_id?: string;
  actor_id: string;
  actor_email: string;
  old_values?: Record<string, any>;
  new_values?: Record<string, any>;
  status: 'success' | 'failure';
  severity: 'info' | 'warning' | 'error';
  timestamp: string;
  ip_address?: string;
  error_message?: string;
}

export interface RemoteCommand {
  id: string;
  command_type: string;
  parameters?: Record<string, any>;
  status: 'pending' | 'executing' | 'completed' | 'failed';
  result?: any;
  created_at: string;
  executed_at?: string;
}

// Authentication Service
export const authService = {
  async login(email: string, password: string): Promise<LoginResponse> {
    return apiClient.post('/api/auth/login', { email, password });
  },

  async register(data: RegisterRequest): Promise<LoginResponse> {
    return apiClient.post('/api/auth/register', data);
  },

  async logout(): Promise<void> {
    apiClient.clearToken();
  },
};

// User Service
export const userService = {
  async getProfile(): Promise<User> {
    return apiClient.get('/api/users/profile');
  },

  async updateProfile(data: Partial<User>): Promise<User> {
    return apiClient.put('/api/users/profile', data);
  },

  async getAllUsers(): Promise<User[]> {
    return apiClient.get('/api/users');
  },

  async getUserById(id: string): Promise<User> {
    return apiClient.get(`/api/users/${id}`);
  },

  async createUser(data: RegisterRequest): Promise<User> {
    return apiClient.post('/api/users', data);
  },

  async updateUser(id: string, data: Partial<User>): Promise<User> {
    return apiClient.put(`/api/users/${id}`, data);
  },

  async deleteUser(id: string): Promise<void> {
    return apiClient.delete(`/api/users/${id}`);
  },

  async changePassword(oldPassword: string, newPassword: string): Promise<void> {
    return apiClient.post('/api/users/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    });
  },
};

// Parameter Service
export const parameterService = {
  async getAllParameters(): Promise<Parameter[]> {
    return apiClient.get('/api/parameters');
  },

  async getParameterById(id: string): Promise<Parameter> {
    return apiClient.get(`/api/parameters/${id}`);
  },

  async createParameter(data: Partial<Parameter>): Promise<Parameter> {
    return apiClient.post('/api/parameters', data);
  },

  async updateParameter(id: string, data: Partial<Parameter>): Promise<Parameter> {
    return apiClient.put(`/api/parameters/${id}`, data);
  },

  async deleteParameter(id: string): Promise<void> {
    return apiClient.delete(`/api/parameters/${id}`);
  },

  async updateParameterValue(id: string, value: number): Promise<Parameter> {
    return apiClient.patch(`/api/parameters/${id}/value`, { value });
  },
};

// Telemetry Service
export const telemetryService = {
  async getLatestTelemetry(): Promise<Telemetry[]> {
    return apiClient.get('/api/telemetry/latest');
  },

  async getParameterLatest(paramId: string): Promise<Telemetry> {
    return apiClient.get(`/api/telemetry/parameter/${paramId}/latest`);
  },

  async getParameterHistory(paramId: string, minutes: number = 60): Promise<Telemetry[]> {
    return apiClient.get(`/api/telemetry/parameter/${paramId}/history`, {
      params: { minutes },
    });
  },

  async getDeviceLatest(deviceId: string): Promise<Telemetry[]> {
    return apiClient.get(`/api/telemetry/device/${deviceId}/latest`);
  },

  async getDeviceHistory(deviceId: string, minutes: number = 60): Promise<Telemetry[]> {
    return apiClient.get(`/api/telemetry/device/${deviceId}/history`, {
      params: { minutes },
    });
  },

  async updateTelemetry(data: TelemetryUpdate): Promise<Telemetry> {
    return apiClient.post('/api/telemetry', data);
  },
};

// Audit Log Service
export const auditLogService = {
  async getLogs(filters?: {
    event_type?: string;
    resource_type?: string;
    severity?: string;
    status?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ logs: AuditLog[]; total: number }> {
    return apiClient.get('/api/audit-logs', { params: filters });
  },

  async getLogById(id: string): Promise<AuditLog> {
    return apiClient.get(`/api/audit-logs/${id}`);
  },

  async getStatistics(filters?: any): Promise<any> {
    return apiClient.get('/api/audit-logs/statistics', { params: filters });
  },

  async exportLogs(format: 'csv' | 'json' = 'csv', filters?: any): Promise<Blob> {
    return apiClient.get(`/api/audit-logs/export?format=${format}`, {
      params: filters,
      responseType: 'blob',
    });
  },
};

// Remote Commands Service
export const remoteCommandService = {
  async executeCommand(commandType: string, parameters?: Record<string, any>): Promise<RemoteCommand> {
    return apiClient.post('/api/commands', {
      command_type: commandType,
      parameters,
    });
  },

  async getCommandStatus(id: string): Promise<RemoteCommand> {
    return apiClient.get(`/api/commands/${id}`);
  },

  async getCommandHistory(limit: number = 50): Promise<RemoteCommand[]> {
    return apiClient.get('/api/commands', { params: { limit } });
  },

  async cancelCommand(id: string): Promise<void> {
    return apiClient.post(`/api/commands/${id}/cancel`);
  },
};

// Configuration Service
export const configService = {
  async getSystemConfig(): Promise<Record<string, any>> {
    return apiClient.get('/api/config/system');
  },

  async updateSystemConfig(data: Record<string, any>): Promise<Record<string, any>> {
    return apiClient.put('/api/config/system', data);
  },

  async getMQTTStatus(): Promise<{ status: 'online' | 'offline'; connected_at?: string }> {
    return apiClient.get('/api/config/mqtt-status');
  },

  async getParameterStream(): Promise<any> {
    return apiClient.get('/api/config/parameter-stream');
  },

  async updateParameterStream(data: any): Promise<any> {
    return apiClient.put('/api/config/parameter-stream', data);
  },
};

// Sync Service
export const syncService = {
  async syncData(): Promise<{ synced_count: number; timestamp: string }> {
    return apiClient.post('/api/sync/data');
  },

  async getSyncStatus(): Promise<any> {
    return apiClient.get('/api/sync/status');
  },

  async resolveSyncConflict(conflictId: string, resolution: 'keep_local' | 'keep_remote'): Promise<void> {
    return apiClient.post(`/api/sync/conflicts/${conflictId}/resolve`, { resolution });
  },
};

// Buffer Service
export const bufferService = {
  async getBufferData(limit: number = 100): Promise<any[]> {
    return apiClient.get('/api/buffer', { params: { limit } });
  },

  async clearBuffer(): Promise<void> {
    return apiClient.post('/api/buffer/clear');
  },

  async flushBuffer(): Promise<{ flushed_count: number }> {
    return apiClient.post('/api/buffer/flush');
  },
};

// Report Service
export const reportService = {
  async generateReport(type: string, filters?: any): Promise<Blob> {
    return apiClient.post(`/api/reports/${type}`, filters, {
      responseType: 'blob',
    });
  },

  async getReportHistory(): Promise<any[]> {
    return apiClient.get('/api/reports/history');
  },
};
