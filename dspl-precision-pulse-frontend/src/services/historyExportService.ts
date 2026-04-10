const API = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

export interface ExportOptions {
  preset: string;
  paramIds: number[];
  startDate?: string;
  endDate?: string;
  token: string;
}

export const historyExportService = {
  async exportPDF(options: ExportOptions): Promise<void> {
    try {
      const { preset, paramIds, startDate, endDate, token } = options;
      
      if (paramIds.length === 0) {
        alert('Please select at least one parameter');
        return;
      }

      const params = new URLSearchParams();
      params.append('preset', preset);
      paramIds.forEach(id => params.append('param_ids', id.toString()));
      
      if (preset === 'custom' && startDate && endDate) {
        params.append('start_date', startDate);
        params.append('end_date', endDate);
      }

      const url = `${API}/api/reports/history/export/pdf?${params.toString()}`;
      
      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error(`Export failed: ${response.statusText}`);
      }

      const blob = await response.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `history_report_${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      console.error('PDF export error:', error);
      alert(`Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  },

  async exportCSV(
    options: ExportOptions,
    allTimestamps: string[],
    valueLookup: Record<number, Record<string, number>>,
    parameters: Array<{ id: number; name: string; unit: string }>
  ): Promise<void> {
    try {
      const { preset, paramIds, token } = options;

      if (paramIds.length === 0) {
        alert('Please select at least one parameter');
        return;
      }

      const selectedParams = parameters.filter(p => paramIds.includes(p.id));
      const header = ['Timestamp', ...selectedParams.map(p => `${p.name} (${p.unit})`)].join(',');
      
      const rows = allTimestamps.map(ts => {
        const timestamp = new Date(ts).toLocaleString();
        const values = selectedParams.map(p => {
          const val = valueLookup[p.id]?.[ts];
          return val !== undefined ? val.toFixed(2) : '';
        });
        return [timestamp, ...values].join(',');
      });

      const csv = [header, ...rows].join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `history_export_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      console.error('CSV export error:', error);
      alert(`Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }
};
