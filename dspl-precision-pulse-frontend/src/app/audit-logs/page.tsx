'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import PaginationControls from '@/components/PaginationControls';
import { auditLogService } from '@/services/auditLogService';

interface AuditLog {
  id: number;
  event_type: string;
  severity: string;
  actor_email: string;
  actor_ip: string;
  resource_type: string;
  resource_id: string;
  resource_name: string;
  action: string;
  description: string;
  old_values: Record<string, any>;
  new_values: Record<string, any>;
  status: string;
  error_message: string;
  created_at: string;
  device_id: string;
}

interface Statistics {
  total_events: number;
  event_distribution: Array<{ event_type: string; count: number }>;
  resource_distribution: Array<{ resource_type: string; count: number }>;
  status_distribution: Array<{ status: string; count: number }>;
  severity_distribution: Array<{ severity: string; count: number }>;
  top_actors: Array<{ actor_email: string; count: number }>;
}

export default function AuditLogsPage() {
  const router = useRouter();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [statistics, setStatistics] = useState<Statistics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  // Filters with default date range (last 7 days)
  const getDefaultFromDate = () => {
    const date = new Date();
    date.setDate(date.getDate() - 7);
    return date.toISOString().slice(0, 16);
  };
  
  const getDefaultToDate = () => {
    return new Date().toISOString().slice(0, 16);
  };
  
  const [eventType, setEventType] = useState('');
  const [resourceType, setResourceType] = useState('');
  const [actorEmail, setActorEmail] = useState('');
  const [severity, setSeverity] = useState('');
  const [status, setStatus] = useState('');
  const [fromDate, setFromDate] = useState(getDefaultFromDate());
  const [toDate, setToDate] = useState(getDefaultToDate());
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const itemsPerPage = 20;
  
  // Event types and resource types
  const [eventTypes, setEventTypes] = useState<string[]>([]);

  // Check authentication
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      setError('Not authenticated. Redirecting to login...');
      setTimeout(() => router.push('/login'), 2000);
      return;
    }
    setIsAuthenticated(true);
  }, [router]);

  // Load event types
  useEffect(() => {
    if (!isAuthenticated) return;

    const loadEventTypes = async () => {
      try {
        const token = localStorage.getItem('token');
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
        
        const res = await fetch(`${backendUrl}/api/audit/events`, {
          headers: { 'Authorization': `Bearer ${token}` },
          credentials: 'include'
        });
        
        if (res.ok) {
          const data = await res.json();
          setEventTypes(data.event_types || []);
        }
      } catch (err) {
        console.error('Error loading event types:', err);
      }
    };
    
    loadEventTypes();
  }, [isAuthenticated]);

  // Load logs and statistics
  useEffect(() => {
    if (isAuthenticated) {
      loadLogs();
      loadStatistics();
    }
  }, [isAuthenticated, currentPage, eventType, resourceType, actorEmail, severity, status, fromDate, toDate]);

  const loadLogs = async () => {
    setLoading(true);
    setError('');
    
    try {
      const token = localStorage.getItem('token');
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
      
      const params = new URLSearchParams({
        limit: itemsPerPage.toString(),
        offset: ((currentPage - 1) * itemsPerPage).toString(),
      });
      
      if (eventType) params.append('event_type', eventType);
      if (resourceType) params.append('resource_type', resourceType);
      if (actorEmail) params.append('actor_email', actorEmail);
      if (fromDate) params.append('start_date', fromDate);
      if (toDate) params.append('end_date', toDate);
      
      const res = await fetch(`${backendUrl}/api/audit/logs?${params}`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include'
      });
      
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
        setTotalCount(data.total_count || 0);
      } else {
        setError(`Failed to load audit logs: ${res.status}`);
      }
    } catch (err) {
      console.error('Error loading logs:', err);
      setError(`Error loading audit logs: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    try {
      const token = localStorage.getItem('token');
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
      
      const res = await fetch(`${backendUrl}/api/audit/statistics?days=7`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include'
      });
      
      if (res.ok) {
        const data = await res.json();
        setStatistics(data);
      }
    } catch (err) {
      console.error('Error loading statistics:', err);
    }
  };

  const handleExport = async () => {
    try {
      const token = localStorage.getItem('token');
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
      
      const res = await fetch(`${backendUrl}/api/audit/export`, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include'
      });
      
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit_logs_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (err) {
      console.error('Error exporting logs:', err);
      setError('Failed to export logs');
    }
  };

  const handleClearFilters = () => {
    setEventType('');
    setResourceType('');
    setActorEmail('');
    setSeverity('');
    setStatus('');
    setFromDate(getDefaultFromDate());
    setToDate(getDefaultToDate());
    setCurrentPage(1);
  };

  const formatDate = (dateString: string): string => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getSeverityColor = (severity: string): string => {
    switch (severity) {
      case 'critical': return 'bg-red-600/20 border-red-500/30 text-red-400';
      case 'error': return 'bg-orange-600/20 border-orange-500/30 text-orange-400';
      case 'warning': return 'bg-yellow-600/20 border-yellow-500/30 text-yellow-400';
      default: return 'bg-blue-600/20 border-blue-500/30 text-blue-400';
    }
  };

  const getStatusColor = (status: string): string => {
    return status === 'success' 
      ? 'bg-green-600/20 border-green-500/30 text-green-400'
      : 'bg-red-600/20 border-red-500/30 text-red-400';
  };

  const totalPages = Math.ceil(totalCount / itemsPerPage);

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
        <div className="text-center">
          <p className="text-white text-lg mb-4">Redirecting to login...</p>
          <p className="text-slate-400">Please wait...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 border-b border-indigo-500/20 sticky top-0 z-50">
        <div className="px-4 sm:px-8 lg:px-20 py-4">
          <h1 className="text-lg sm:text-2xl font-bold text-white">Audit Logs</h1>
          <p className="text-xs sm:text-sm text-slate-400">Monitor system activity and security events</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="px-4 sm:px-8 lg:px-20 py-8">
        {/* Statistics Cards */}
        {statistics && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
            <div className="bg-blue-600/20 border border-blue-500/30 rounded-lg p-4">
              <div className="text-slate-400 text-xs font-medium">Total Events</div>
              <div className="text-2xl font-bold text-blue-400 mt-1">{statistics.total_events}</div>
            </div>
            
            <div className="bg-green-600/20 border border-green-500/30 rounded-lg p-4">
              <div className="text-slate-400 text-xs font-medium">Success</div>
              <div className="text-2xl font-bold text-green-400 mt-1">
                {statistics.status_distribution.find(s => s.status === 'success')?.count || 0}
              </div>
            </div>
            
            <div className="bg-red-600/20 border border-red-500/30 rounded-lg p-4">
              <div className="text-slate-400 text-xs font-medium">Failures</div>
              <div className="text-2xl font-bold text-red-400 mt-1">
                {statistics.status_distribution.find(s => s.status === 'failure')?.count || 0}
              </div>
            </div>
            
            <div className="bg-purple-600/20 border border-purple-500/30 rounded-lg p-4">
              <div className="text-slate-400 text-xs font-medium">Critical</div>
              <div className="text-2xl font-bold text-purple-400 mt-1">
                {statistics.severity_distribution.find(s => s.severity === 'critical')?.count || 0}
              </div>
            </div>
            
            <div className="bg-yellow-600/20 border border-yellow-500/30 rounded-lg p-4">
              <div className="text-slate-400 text-xs font-medium">Warnings</div>
              <div className="text-2xl font-bold text-yellow-400 mt-1">
                {statistics.severity_distribution.find(s => s.severity === 'warning')?.count || 0}
              </div>
            </div>
          </div>
        )}

        {/* Filters Section */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Filters</h2>
            {(eventType || resourceType || actorEmail || severity || status || fromDate !== getDefaultFromDate() || toDate !== getDefaultToDate()) && (
              <button
                onClick={handleClearFilters}
                className="text-xs text-red-400 hover:text-red-300 font-semibold transition-colors"
              >
                Clear All
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            {/* Event Type */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">Event Type</label>
              <select
                value={eventType}
                onChange={(e) => {
                  setEventType(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:border-indigo-500 focus:outline-none text-sm"
              >
                <option value="">All Events</option>
                {eventTypes.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>

            {/* Resource Type */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">Resource Type</label>
              <select
                value={resourceType}
                onChange={(e) => {
                  setResourceType(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:border-indigo-500 focus:outline-none text-sm"
              >
                <option value="">All Resources</option>
                <option value="user">User</option>
                <option value="config">Configuration</option>
                <option value="command">Command</option>
                <option value="parameter">Parameter</option>
                <option value="telemetry">Telemetry</option>
                <option value="security">Security</option>
              </select>
            </div>

            {/* Severity */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">Severity</label>
              <select
                value={severity}
                onChange={(e) => {
                  setSeverity(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:border-indigo-500 focus:outline-none text-sm"
              >
                <option value="">All Severities</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="critical">Critical</option>
              </select>
            </div>

            {/* Status */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">Status</label>
              <select
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:border-indigo-500 focus:outline-none text-sm"
              >
                <option value="">All Status</option>
                <option value="success">Success</option>
                <option value="failure">Failure</option>
              </select>
            </div>
          </div>

          {/* Date Range */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">From Date</label>
              <input
                type="datetime-local"
                value={fromDate}
                onChange={(e) => {
                  setFromDate(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:border-indigo-500 focus:outline-none text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">To Date</label>
              <input
                type="datetime-local"
                value={toDate}
                onChange={(e) => {
                  setToDate(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:border-indigo-500 focus:outline-none text-sm"
              />
            </div>
          </div>

          
          {/* Export Button */}
          <button
            onClick={handleExport}
            className="w-full px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-semibold text-sm transition-colors"
          >
            Export as CSV
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-600/20 border border-red-500/30 rounded-lg p-4 mb-8">
            <p className="text-red-400 font-semibold text-sm">{error}</p>
          </div>
        )}

        {/* Audit Logs Table */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-700">
            <h2 className="text-lg font-semibold text-white">Audit Logs</h2>
            <p className="text-slate-400 text-xs mt-1">
              Showing {logs.length > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0} to {Math.min(currentPage * itemsPerPage, totalCount)} of {totalCount} logs
            </p>
          </div>

          {loading ? (
            <div className="p-8 text-center">
              <p className="text-slate-400 text-sm">Loading audit logs...</p>
            </div>
          ) : logs.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-slate-700/50 border-b border-slate-600">
                    <tr>
                      <th className="px-6 py-3 text-left text-slate-300 font-semibold">Timestamp</th>
                      <th className="px-6 py-3 text-left text-slate-300 font-semibold">Event Type</th>
                      <th className="px-6 py-3 text-left text-slate-300 font-semibold">Resource</th>
                      <th className="px-6 py-3 text-left text-slate-300 font-semibold">Actor</th>
                      <th className="px-6 py-3 text-left text-slate-300 font-semibold">Action</th>
                      <th className="px-6 py-3 text-left text-slate-300 font-semibold">Severity</th>
                      <th className="px-6 py-3 text-left text-slate-300 font-semibold">Status</th>
                      <th className="px-6 py-3 text-left text-slate-300 font-semibold">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log, idx) => (
                      <tr key={idx} className="border-b border-slate-700 hover:bg-slate-700/30 transition-colors">
                        <td className="px-6 py-3 text-slate-300 whitespace-nowrap">
                          {formatDate(log.created_at)}
                        </td>
                        <td className="px-6 py-3 text-slate-300">
                          <span className="px-2 py-1 bg-slate-700 rounded text-xs">{log.event_type}</span>
                        </td>
                        <td className="px-6 py-3 text-slate-300">
                          <div className="text-xs">
                            <div className="font-semibold">{log.resource_type}</div>
                            <div className="text-slate-500">{log.resource_id}</div>
                          </div>
                        </td>
                        <td className="px-6 py-3 text-slate-300 text-xs">
                          {log.actor_email || 'System'}
                        </td>
                        <td className="px-6 py-3 text-slate-300 text-xs">
                          {log.action}
                        </td>
                        <td className="px-6 py-3">
                          <span className={`px-2 py-1 rounded text-xs border ${getSeverityColor(log.severity)}`}>
                            {log.severity}
                          </span>
                        </td>
                        <td className="px-6 py-3">
                          <span className={`px-2 py-1 rounded text-xs border ${getStatusColor(log.status)}`}>
                            {log.status}
                          </span>
                        </td>
                        <td className="px-6 py-3 text-slate-300 text-xs max-w-xs truncate">
                          {log.description}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="px-6 py-4 border-t border-slate-700 flex items-center justify-between bg-slate-700/20">
                <div className="text-xs text-slate-400">
                  Page {currentPage} of {totalPages}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                    disabled={currentPage === 1}
                    className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 text-slate-300 rounded text-xs font-semibold transition-colors"
                  >
                    Prev
                  </button>
                  <div className="flex items-center gap-1">
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      const page = i + 1;
                      return (
                        <button
                          key={page}
                          onClick={() => setCurrentPage(page)}
                          className={`px-2 py-1 rounded text-xs font-semibold transition-colors ${
                            currentPage === page
                              ? 'bg-indigo-600 text-white'
                              : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                          }`}
                        >
                          {page}
                        </button>
                      );
                    })}
                  </div>
                  <button
                    onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                    disabled={currentPage === totalPages}
                    className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 text-slate-300 rounded text-xs font-semibold transition-colors"
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="p-8 text-center">
              <p className="text-slate-400 text-sm">No audit logs found</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
