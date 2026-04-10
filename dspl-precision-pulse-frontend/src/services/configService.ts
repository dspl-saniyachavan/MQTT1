const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

export interface SystemConfig {
  id: number;
  key: string;
  value: string;
  description: string;
  category: string;
  data_type: 'string' | 'integer' | 'boolean' | 'json';
  is_sensitive: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  updated_by: string;
}

export interface ConfigResponse {
  configs: SystemConfig[];
  count: number;
  global_version: number;
}

export interface CategoryResponse {
  categories: string[];
}

export interface VersionResponse {
  version: number;
  timestamp: string;
}

class ConfigService {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
  }

  private getHeaders() {
    return {
      'Authorization': `Bearer ${this.token}`,
      'Content-Type': 'application/json',
    };
  }

  async getAllConfigs(category?: string): Promise<ConfigResponse> {
    try {
      const url = new URL(`${BACKEND_URL}/api/config/`);
      if (category) {
        url.searchParams.append('category', category);
      }

      const res = await fetch(url.toString(), {
        headers: this.getHeaders(),
      });

      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.error || `HTTP ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      console.error('[CONFIG_SERVICE] Error fetching configs:', err);
      throw err;
    }
  }

  async getConfig(key: string): Promise<{ config: SystemConfig }> {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/${key}`, {
        headers: this.getHeaders(),
      });

      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.error || `HTTP ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      console.error('[CONFIG_SERVICE] Error fetching config:', err);
      throw err;
    }
  }

  async createConfig(data: {
    key: string;
    value: string;
    description?: string;
    category?: string;
    data_type?: string;
    is_sensitive?: boolean;
  }): Promise<{ message: string; config: SystemConfig }> {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.error || `HTTP ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      console.error('[CONFIG_SERVICE] Error creating config:', err);
      throw err;
    }
  }

  async updateConfig(
    key: string,
    data: {
      value?: string;
      description?: string;
      category?: string;
      data_type?: string;
      is_sensitive?: boolean;
    }
  ): Promise<{ message: string; config: SystemConfig }> {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/${key}`, {
        method: 'PUT',
        headers: this.getHeaders(),
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.error || `HTTP ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      console.error('[CONFIG_SERVICE] Error updating config:', err);
      throw err;
    }
  }

  async deleteConfig(key: string): Promise<{ message: string }> {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/${key}`, {
        method: 'DELETE',
        headers: this.getHeaders(),
      });

      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.error || `HTTP ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      console.error('[CONFIG_SERVICE] Error deleting config:', err);
      throw err;
    }
  }

  async bulkUpdateConfigs(configs: Array<{ key: string; value: string }>): Promise<{
    message: string;
    count: number;
    configs: SystemConfig[];
  }> {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/bulk-update`, {
        method: 'PUT',
        headers: this.getHeaders(),
        body: JSON.stringify({ configs }),
      });

      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.error || `HTTP ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      console.error('[CONFIG_SERVICE] Error bulk updating configs:', err);
      throw err;
    }
  }

  async getCategories(): Promise<CategoryResponse> {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/categories`, {
        headers: this.getHeaders(),
      });

      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.error || `HTTP ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      console.error('[CONFIG_SERVICE] Error fetching categories:', err);
      throw err;
    }
  }

  async getConfigVersion(): Promise<VersionResponse> {
    try {
      const res = await fetch(`${BACKEND_URL}/api/config/version`, {
        headers: this.getHeaders(),
      });

      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.error || `HTTP ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      console.error('[CONFIG_SERVICE] Error fetching version:', err);
      throw err;
    }
  }
}

export const configService = new ConfigService();
