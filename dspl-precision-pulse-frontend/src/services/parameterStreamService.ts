import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

export interface ParameterStreamData {
  id: number;
  device_id: string;
  parameter_id: number;
  parameter_name: string;
  value: number;
  unit: string;
  min: number;
  max: number;
  color: string;
  timestamp: string;
  created_at: string;
}

export const parameterStreamService = {
  /**
   * Get latest parameter streaming data for all parameters
   */
  async getLatestParameterStream(): Promise<ParameterStreamData[]> {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/parameter-stream/latest`);
      return response.data.parameters || [];
    } catch (error) {
      console.error('Error fetching latest parameter stream:', error);
      return [];
    }
  },

  /**
   * Get latest parameter streaming data from a specific device
   */
  async getDeviceParameterStream(deviceId: string): Promise<ParameterStreamData[]> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/parameter-stream/device/${deviceId}/latest`
      );
      return response.data.parameters || [];
    } catch (error) {
      console.error(`Error fetching parameter stream for device ${deviceId}:`, error);
      return [];
    }
  },

  /**
   * Get historical parameter streaming data (last N minutes)
   */
  async getParameterStreamHistory(
    paramId: number,
    minutes: number = 1
  ): Promise<ParameterStreamData[]> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/parameter-stream/parameter/${paramId}/history?minutes=${minutes}`
      );
      return response.data.data || [];
    } catch (error) {
      console.error(`Error fetching parameter stream history for parameter ${paramId}:`, error);
      return [];
    }
  },

  /**
   * Update parameter value (admin only) - replaces old value with new value
   */
  async updateParameterValue(
    paramId: number,
    value: number,
    token: string
  ): Promise<{ success: boolean; message: string; data?: any }> {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/parameter-stream/parameter/${paramId}/value`,
        { value },
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );
      return {
        success: true,
        message: response.data.message,
        data: response.data
      };
    } catch (error: any) {
      const errorMsg = error.response?.data?.error || 'Failed to update parameter';
      console.error('Error updating parameter value:', errorMsg);
      return {
        success: false,
        message: errorMsg
      };
    }
  }
};
