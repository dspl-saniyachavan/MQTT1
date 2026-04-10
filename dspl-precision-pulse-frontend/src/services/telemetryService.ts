import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

export const telemetryService = {
  /**
   * Get latest telemetry data for all parameters
   */
  async getLatestTelemetry() {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/telemetry/latest`);
      return response.data.telemetry || [];
    } catch (error) {
      console.error('Error fetching latest telemetry:', error);
      return [];
    }
  },

  /**
   * Get latest value for a specific parameter
   */
  async getParameterLatest(paramId: string | number) {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/telemetry/parameter/${paramId}/latest`
      );
      return response.data.telemetry;
    } catch (error) {
      console.error(`Error fetching latest for parameter ${paramId}:`, error);
      return null;
    }
  },

  /**
   * Get historical data for a parameter (last N minutes)
   */
  async getParameterHistory(paramId: string | number, minutes: number = 1) {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/telemetry/parameter/${paramId}/history?minutes=${minutes}`
      );
      return response.data.data || [];
    } catch (error) {
      console.error(`Error fetching history for parameter ${paramId}:`, error);
      return [];
    }
  },

  /**
   * Get latest telemetry from a specific device
   */
  async getDeviceLatest(deviceId: string | number) {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/telemetry/device/${deviceId}/latest`
      );
      return response.data.telemetry || [];
    } catch (error) {
      console.error(`Error fetching telemetry for device ${deviceId}:`, error);
      return [];
    }
  },
};
