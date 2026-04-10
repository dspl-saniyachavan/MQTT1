"""
Report generation service for streamed telemetry data
Generates reports from telemetry streams with aggregation and statistics
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import json
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_COL_START_TIME = _COL_START_TIME
_COL_END_TIME = _COL_END_TIME
_COL_DEVICE_ID = _COL_DEVICE_ID

class ReportFormat(Enum):
    """Report export formats"""
    PDF = 'pdf'
    EXCEL = 'excel'
    CSV = 'csv'
    JSON = 'json'

class TelemetryReport:
    """Report generated from telemetry data"""
    
    def __init__(self, report_id: int, parameter_name: str, start_time: datetime, 
                 end_time: datetime, data_points: List[Dict]):
        self.report_id = report_id
        self.parameter_name = parameter_name
        self.start_time = start_time
        self.end_time = end_time
        self.data_points = data_points
        self.created_at = datetime.now(timezone.utc)
        self.statistics = self._calculate_statistics()
    
    def _calculate_statistics(self) -> Dict:
        """Calculate statistics from data points"""
        if not self.data_points:
            return {}
        
        values = [dp.get('value', 0) for dp in self.data_points if isinstance(dp.get('value'), (int, float))]
        
        if not values:
            return {}
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'sum': sum(values),
            'first_value': values[0],
            'last_value': values[-1],
            'unit': self.data_points[0].get('unit', '') if self.data_points else ''
        }
    
    def to_dict(self) -> dict:
        return {
            'report_id': self.report_id,
            'parameter_name': self.parameter_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'data_points_count': len(self.data_points),
            'statistics': self.statistics,
            'created_at': self.created_at.isoformat()
        }

class TelemetryReportService:
    """Service for generating reports from telemetry data"""
    
    def __init__(self, sqlite_path: str = None):
        self.sqlite_path = sqlite_path or 'data/precision_pulse.db'
        self.report_counter = 0
        self.reports: Dict[int, TelemetryReport] = {}
    
    def generate_parameter_report(self, parameter_name: str, start_time: datetime, 
                                 end_time: datetime) -> Tuple[bool, Optional[int], Optional[str]]:
        """Generate report for parameter within time range"""
        try:
            if not Path(self.sqlite_path).exists():
                return False, None, f"Database not found at {self.sqlite_path}"
            
            # Fetch telemetry data
            data_points = self._fetch_telemetry_data(parameter_name, start_time, end_time)
            
            if not data_points:
                return False, None, f"No data found for {parameter_name} in time range"
            
            self.report_counter += 1
            report = TelemetryReport(
                self.report_counter,
                parameter_name,
                start_time,
                end_time,
                data_points
            )
            self.reports[self.report_counter] = report
            
            logger.info(f"[TELEMETRY_REPORT] Generated report {self.report_counter} for {parameter_name}")
            return True, self.report_counter, None
        
        except Exception as e:
            logger.error(f"[TELEMETRY_REPORT] Error generating report: {e}")
            return False, None, str(e)
    
    def generate_multi_parameter_report(self, parameter_names: List[str], 
                                       start_time: datetime, end_time: datetime) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Generate report for multiple parameters"""
        try:
            report_data = {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'parameters': {},
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
            for param_name in parameter_names:
                data_points = self._fetch_telemetry_data(param_name, start_time, end_time)
                if data_points:
                    report = TelemetryReport(0, param_name, start_time, end_time, data_points)
                    report_data['parameters'][param_name] = report.to_dict()
            
            if not report_data['parameters']:
                return False, None, "No data found for any parameters"
            
            logger.info(f"[TELEMETRY_REPORT] Generated multi-parameter report for {len(parameter_names)} parameters")
            return True, report_data, None
        
        except Exception as e:
            logger.error(f"[TELEMETRY_REPORT] Error generating multi-parameter report: {e}")
            return False, None, str(e)
    
    def _fetch_telemetry_data(self, parameter_name: str, start_time: datetime, 
                             end_time: datetime) -> List[Dict]:
        """Fetch telemetry data from SQLite"""
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''\
                    SELECT id, parameter_id, parameter_name, value, unit, timestamp, device_id, status
                    FROM telemetry_data
                    WHERE parameter_name = ? AND timestamp BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                ''', (parameter_name, start_time.isoformat(), end_time.isoformat()))
                
                return [dict(row) for row in cursor.fetchall()]
        
        except Exception as e:
            logger.error(f"[TELEMETRY_REPORT] Error fetching telemetry data: {e}")
            return []
    
    def export_report(self, report_id: int, format: ReportFormat) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """Export report to specified format"""
        try:
            if report_id not in self.reports:
                return False, None, "Report not found"
            
            report = self.reports[report_id]
            
            if format == ReportFormat.JSON:
                data = json.dumps(report.to_dict(), indent=2).encode()
                return True, data, None
            
            elif format == ReportFormat.CSV:
                return self._export_csv(report)
            
            elif format == ReportFormat.EXCEL:
                return self._export_excel(report)
            
            elif format == ReportFormat.PDF:
                return self._export_pdf(report)
            
            return False, None, f"Unsupported format: {format}"
        
        except Exception as e:
            logger.error(f"[TELEMETRY_REPORT] Error exporting report: {e}")
            return False, None, str(e)
    
    def _export_csv(self, report: TelemetryReport) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """Export report as CSV"""
        try:
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow(['Telemetry Report'])
            writer.writerow(['Parameter', report.parameter_name])
            writer.writerow([_COL_START_TIME, report.start_time.isoformat()])
            writer.writerow([_COL_END_TIME, report.end_time.isoformat()])
            writer.writerow(['Generated', report.created_at.isoformat()])
            writer.writerow([])
            
            # Statistics
            writer.writerow(['Statistics'])
            for key, value in report.statistics.items():
                writer.writerow([key.replace('_', ' ').title(), value])
            writer.writerow([])
            
            # Data points
            writer.writerow(['Timestamp', 'Value', 'Unit', _COL_DEVICE_ID, 'Status'])
            for dp in report.data_points:
                writer.writerow([
                    dp.get('timestamp', ''),
                    dp.get('value', ''),
                    dp.get('unit', ''),
                    dp.get('device_id', ''),
                    dp.get('status', '')
                ])
            
            return True, output.getvalue().encode(), None
        
        except Exception as e:
            logger.error(f"[TELEMETRY_REPORT] Error exporting CSV: {e}")
            return False, None, str(e)
    
    def _export_excel(self, report: TelemetryReport) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """Export report as Excel"""
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Report"
            
            # Header
            ws['A1'] = 'Telemetry Report'
            ws['A1'].font = Font(bold=True, size=14)
            
            ws['A2'] = 'Parameter'
            ws['B2'] = report.parameter_name
            
            ws['A3'] = _COL_START_TIME
            ws['B3'] = report.start_time.isoformat()
            
            ws['A4'] = _COL_END_TIME
            ws['B4'] = report.end_time.isoformat()
            
            ws['A5'] = 'Generated'
            ws['B5'] = report.created_at.isoformat()
            
            # Statistics
            row = 7
            ws[f'A{row}'] = 'Statistics'
            ws[f'A{row}'].font = Font(bold=True)
            row += 1
            
            for key, value in report.statistics.items():
                ws[f'A{row}'] = key.replace('_', ' ').title()
                ws[f'B{row}'] = value
                row += 1
            
            # Data points
            row += 1
            headers = ['Timestamp', 'Value', 'Unit', _COL_DEVICE_ID, 'Status']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=row, column=col)
                cell.value = header
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
            
            row += 1
            for dp in report.data_points:
                ws.cell(row=row, column=1).value = dp.get('timestamp', '')
                ws.cell(row=row, column=2).value = dp.get('value', '')
                ws.cell(row=row, column=3).value = dp.get('unit', '')
                ws.cell(row=row, column=4).value = dp.get('device_id', '')
                ws.cell(row=row, column=5).value = dp.get('status', '')
                row += 1
            
            # Auto-adjust column widths
            for col in ['A', 'B', 'C', 'D', 'E']:
                ws.column_dimensions[col].width = 20
            
            import io
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return True, output.getvalue(), None
        
        except ImportError:
            return False, None, "openpyxl not installed"
        except Exception as e:
            logger.error(f"[TELEMETRY_REPORT] Error exporting Excel: {e}")
            return False, None, str(e)
    
    def _export_pdf(self, report: TelemetryReport) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """Export report as PDF"""
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            import io
            
            output = io.BytesIO()
            doc = SimpleDocTemplate(output, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                textColor=colors.HexColor('#1e293b'),
                spaceAfter=12
            )
            elements.append(Paragraph(f"Telemetry Report: {report.parameter_name}", title_style))
            elements.append(Spacer(1, 0.2*inch))
            
            # Metadata
            metadata = [
                [_COL_START_TIME, report.start_time.isoformat()],
                [_COL_END_TIME, report.end_time.isoformat()],
                ['Generated', report.created_at.isoformat()],
                ['Data Points', str(len(report.data_points))]
            ]
            
            metadata_table = Table(metadata, colWidths=[2*inch, 4*inch])
            metadata_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e5e7eb')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(metadata_table)
            elements.append(Spacer(1, 0.3*inch))
            
            # Statistics
            elements.append(Paragraph("Statistics", styles['Heading2']))
            stats_data = [['Metric', 'Value']]
            for key, value in report.statistics.items():
                stats_data.append([key.replace('_', ' ').title(), str(value)])
            
            stats_table = Table(stats_data, colWidths=[2*inch, 4*inch])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(stats_table)
            elements.append(Spacer(1, 0.3*inch))
            
            # Data points table (limited to first 50 rows)
            elements.append(Paragraph("Data Points (First 50)", styles['Heading2']))
            data_table_data = [['Timestamp', 'Value', 'Unit', _COL_DEVICE_ID, 'Status']]
            for dp in report.data_points[:50]:
                data_table_data.append([
                    dp.get('timestamp', '')[:19],  # Truncate timestamp
                    str(dp.get('value', '')),
                    dp.get('unit', ''),
                    dp.get('device_id', ''),
                    dp.get('status', '')
                ])
            
            data_table = Table(data_table_data, colWidths=[1.2*inch, 1*inch, 0.8*inch, 1*inch, 0.8*inch])
            data_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey)
            ]))
            elements.append(data_table)
            
            doc.build(elements)
            output.seek(0)
            return True, output.getvalue(), None
        
        except ImportError:
            return False, None, "reportlab not installed"
        except Exception as e:
            logger.error(f"[TELEMETRY_REPORT] Error exporting PDF: {e}")
            return False, None, str(e)
    
    def get_report(self, report_id: int) -> Optional[TelemetryReport]:
        """Get report by ID"""
        return self.reports.get(report_id)
    
    def get_all_reports(self) -> List[dict]:
        """Get all generated reports"""
        return [r.to_dict() for r in self.reports.values()]

# Global instance
_telemetry_report_service = None

def get_telemetry_report_service() -> TelemetryReportService:
    """Get or create telemetry report service"""
    global _telemetry_report_service
    if _telemetry_report_service is None:
        _telemetry_report_service = TelemetryReportService()
    return _telemetry_report_service
