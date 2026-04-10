'use client';

import { useEffect, useState } from 'react';
import { socketIOService } from '@/services/socketIOService';
import { parameterStreamService } from '@/services/parameterStreamService';

interface TelemetryData {
  parameter_id: number;
  parameter_name: string;
  value: number;
  unit: string;
  timestamp: string;
  min?: number;
  max?: number;
  color?: string;
}

interface FilterOptions {
  minValue?: number;
  maxValue?: number;
  parameterIds?: number[];
  timeRange?: number;
}

export default function TelemetryDashboard() {
  const [telemetry, setTelemetry] = useState<TelemetryData[]>([]);
  const [filteredTelemetry, setFilteredTelemetry] = useState<TelemetryData[]>([]);
  const [loading, setLoading] = useState(true);
  const [mqttConnected, setMqttConnected] = useState(false);
  const [filters, setFilters] = useState<FilterOptions>({});
  const [selectedParameter, setSelectedParameter] = useState<number | null>(null);
  const [chartData, setChartData] = useState<any[]>([]);
  const [lastUpdate, setLastUpdate] = useState<string>('');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    console.log('[TELEMETRY] Initializing Socket.IO connection');
    socketIOService.connect();

    const fetchInitial = async () => {
      try {
        console.log('[TELEMETRY] Fetching initial data from API');
        const data = await parameterStreamService.getLatestParameterStream();
        console.log('[TELEMETRY] Initial data received:', data);
        if (data && data.length > 0) {
          setTelemetry(data);
          setFilteredTelemetry(data);
          setError('');
        } else {
          console.log('[TELEMETRY] No initial data from API, waiting for Socket.IO');
        }
      } catch (error) {
        console.error('[TELEMETRY] Error fetching initial data:', error);
        setError('Failed to fetch initial data. Waiting for real-time updates...');
      } finally {
        setLoading(false);
      }
    };

    fetchInitial();

    const handleMqttConnected = () => {
      console.log('[TELEMETRY] MQTT connected event received');
      setMqttConnected(true);
      setError('');
    };

    const handleMqttDisconnected = () => {
      console.log('[TELEMETRY] MQTT disconnected event received');
      setMqttConnected(false);
      setError('MQTT connection lost. Charts and data updates paused.');
      setChartData([]);
      setLastUpdate('');
    };

    const handleMqttStatus = (data: any) => {
      console.log('[TELEMETRY] MQTT status:', data);
      if (data && data.status === 'online') {
        setMqttConnected(true);
        setError('');
      } else {
        setMqttConnected(false);
        setError('MQTT connection lost. Charts and data updates paused.');
        setChartData([]);
        setLastUpdate('');
      }
    };

    const handleTelemetry = (data: any) => {
      console.log('[TELEMETRY] Received telemetry data:', data);
      
      if (!mqttConnected) {
        console.log('[TELEMETRY] MQTT disconnected - ignoring telemetry update');
        return;
      }
      
      if (data && data.data && data.data.parameters) {
        const params = data.data.parameters.map((p: any) => ({
          parameter_id: p.id || p.parameter_id,
          parameter_name: p.name,
          value: p.value,
          unit: p.unit,
          timestamp: data.timestamp || data.data.timestamp || new Date().toISOString(),
          min: p.min,
          max: p.max,
          color: p.color,
        }));
        
        console.log('[TELEMETRY] Processed parameters:', params);
        setTelemetry(params);
        setLastUpdate(new Date().toLocaleTimeString());
        setError('');
        
        applyFilters(params, filters);
        
        if (selectedParameter) {
          updateChart(params);
        }
      } else {
        console.warn('[TELEMETRY] Invalid telemetry data format:', data);
      }
    };

    const handleParameterStreamUpdate = (data: any) => {
      console.log('[TELEMETRY] Received parameter_stream_update:', data);
      handleTelemetry(data);
    };

    socketIOService.on('mqtt_connected', handleMqttConnected);
    socketIOService.on('mqtt_disconnected', handleMqttDisconnected);
    socketIOService.on('mqtt_status', handleMqttStatus);
    socketIOService.on('telemetry', handleTelemetry);
    socketIOService.on('parameter_stream_update', handleParameterStreamUpdate);

    return () => {
      console.log('[TELEMETRY] Cleaning up Socket.IO listeners');
      socketIOService.off('telemetry', handleTelemetry);
      socketIOService.off('parameter_stream_update', handleParameterStreamUpdate);
      socketIOService.off('mqtt_connected', handleMqttConnected);
      socketIOService.off('mqtt_disconnected', handleMqttDisconnected);
      socketIOService.off('mqtt_status', handleMqttStatus);
    };
  }, [mqttConnected, filters, selectedParameter]);

  const applyFilters = (data: TelemetryData[], filterOptions: FilterOptions) => {
    let filtered = [...data];

    if (filterOptions.minValue !== undefined) {
      filtered = filtered.filter(t => t.value >= filterOptions.minValue!);
    }

    if (filterOptions.maxValue !== undefined) {
      filtered = filtered.filter(t => t.value <= filterOptions.maxValue!);
    }

    if (filterOptions.parameterIds && filterOptions.parameterIds.length > 0) {
      filtered = filtered.filter(t => filterOptions.parameterIds!.includes(t.parameter_id));
    }

    setFilteredTelemetry(filtered);
  };

  const handleFilterChange = (newFilters: FilterOptions) => {
    setFilters(newFilters);
    applyFilters(telemetry, newFilters);
  };

  const updateChart = (data: TelemetryData[]) => {
    const paramData = data.filter(t => t.parameter_id === selectedParameter);
    if (paramData.length > 0) {
      setChartData(paramData);
    }
  };

  const handleParameterSelect = async (paramId: number) => {
    setSelectedParameter(paramId);
    try {
      console.log('[TELEMETRY] Fetching history for parameter:', paramId);
      const history = await parameterStreamService.getParameterStreamHistory(paramId, 60);
      console.log('[TELEMETRY] History received:', history);
      if (history && history.length > 0) {
        setChartData(history);
      }
    } catch (error) {
      console.error('[TELEMETRY] Error fetching parameter history:', error);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center">
        <p className="text-gray-600">Loading telemetry dashboard...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      {/* Header with MQTT Status */}
      <div className="mb-8">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-800">Telemetry Dashboard</h1>
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${mqttConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span className="text-sm font-medium">
              {mqttConnected ? 'MQTT Connected' : 'MQTT Disconnected'}
            </span>
            {lastUpdate && (
              <span className="text-xs text-gray-500 ml-4">Last update: {lastUpdate}</span>
            )}
          </div>
        </div>
        
        {!mqttConnected && (
          <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-sm text-yellow-800">
              ⚠️ MQTT is disconnected. Charts will not update until connection is restored.
            </p>
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm text-blue-800">
              ℹ️ {error}
            </p>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="mb-8 bg-white rounded-lg p-6 shadow-md">
        <h2 className="text-lg font-semibold mb-4">Filters</h2>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Min Value
            </label>
            <input
              type="number"
              onChange={(e) => handleFilterChange({
                ...filters,
                minValue: e.target.value ? parseFloat(e.target.value) : undefined
              })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              placeholder="Min"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Max Value
            </label>
            <input
              type="number"
              onChange={(e) => handleFilterChange({
                ...filters,
                maxValue: e.target.value ? parseFloat(e.target.value) : undefined
              })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              placeholder="Max"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Time Range (minutes)
            </label>
            <select
              onChange={(e) => handleFilterChange({
                ...filters,
                timeRange: parseInt(e.target.value)
              })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="60">Last 1 hour</option>
              <option value="360">Last 6 hours</option>
              <option value="1440">Last 24 hours</option>
            </select>
          </div>
        </div>
      </div>

      {/* Telemetry Grid */}
      <div className="grid grid-cols-3 gap-4">
        {!mqttConnected ? (
          <div className="col-span-3 text-center py-12 bg-white rounded-lg border border-gray-200">
            <p className="text-gray-500 text-lg">⚠️ MQTT Disconnected</p>
            <p className="text-sm text-gray-400 mt-2">Waiting for MQTT connection to resume data updates...</p>
          </div>
        ) : filteredTelemetry.length > 0 ? (
          filteredTelemetry.map((item) => (
            <div
              key={item.parameter_id}
              onClick={() => handleParameterSelect(item.parameter_id)}
              className="bg-white rounded-lg p-6 shadow-md cursor-pointer hover:shadow-lg transition-shadow"
            >
              <h3 className="text-lg font-semibold text-gray-800">
                {item.parameter_name}
              </h3>
              <p className="text-4xl font-bold text-blue-600 mt-4">
                {parseFloat(String(item.value)).toFixed(2)}
              </p>
              <p className="text-sm text-gray-600 mt-2">{item.unit}</p>
              {item.min !== undefined && item.max !== undefined && (
                <p className="text-xs text-gray-500 mt-2">
                  Range: {item.min} - {item.max}
                </p>
              )}
              <p className="text-xs text-gray-400 mt-3">
                {new Date(item.timestamp).toLocaleTimeString()}
              </p>
            </div>
          ))
        ) : (
          <div className="col-span-3 text-center py-12">
            <p className="text-gray-500">No telemetry data available</p>
            <p className="text-sm text-gray-400 mt-2">
              Waiting for data from MQTT broker...
            </p>
          </div>
        )}
      </div>

      {/* Detailed Chart View */}
      {selectedParameter && chartData.length > 0 && mqttConnected && (
        <div className="mt-8 bg-white rounded-lg p-6 shadow-md">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold">
              {chartData[0]?.parameter_name} - Historical Data
            </h2>
            <button
              onClick={() => setSelectedParameter(null)}
              className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300"
            >
              Close
            </button>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-4 py-2 text-left">Timestamp</th>
                  <th className="px-4 py-2 text-left">Value</th>
                  <th className="px-4 py-2 text-left">Unit</th>
                </tr>
              </thead>
              <tbody>
                {chartData.slice(0, 20).map((item, idx) => (
                  <tr key={idx} className="border-t">
                    <td className="px-4 py-2">
                      {new Date(item.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 font-semibold">
                      {parseFloat(String(item.value)).toFixed(2)}
                    </td>
                    <td className="px-4 py-2">{item.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
