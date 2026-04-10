"""
Enhanced report generation service with templates and export
"""
import logging
import json
import csv
import io
from datetime import datetime, timedelta, timezone
from app.models import db
from app.models.report_template import ReportTemplate
from app.models.parameter_stream import ParameterStream
from app.models.parameter import Parameter
from app.models.user import User
from sqlalchemy import func

logger = logging.getLogger(__name__)

# Alert thresholds per parameter name. If not defined, ±3σ from mean is used.
ALERT_THRESHOLDS: dict = {
    # 'Temperature': {'min': 0, 'max': 100},
}


class ReportService:
    """Generate reports from parameter_stream data with export support"""

    @staticmethod
    def create_template(name: str, description: str, template_config: dict, created_by: str, is_public: bool = False):
        try:
            template = ReportTemplate(
                name=name, description=description,
                template_config=template_config,
                created_by=created_by, is_public=is_public
            )
            db.session.add(template)
            db.session.commit()
            return template.to_dict()
        except Exception as e:
            logger.error(f"[REPORT] Error creating template: {e}")
            return None

    @staticmethod
    def get_templates(include_private=False):
        try:
            q = ReportTemplate.query if include_private else ReportTemplate.query.filter_by(is_public=True)
            return [t.to_dict() for t in q.all()]
        except Exception as e:
            logger.error(f"[REPORT] Error getting templates: {e}")
            return []

    @staticmethod
    def _parse_dates(start_date, end_date):
        import time as _time
        # Local UTC offset in seconds (e.g. IST = +19800)
        local_offset = timedelta(seconds=-_time.timezone if not _time.daylight else -_time.altzone)

        if not start_date:
            return datetime.now() - timedelta(days=7), datetime.now() + timedelta(minutes=30)
        if not end_date:
            end_date = datetime.now(timezone.utc).isoformat()

        # Strip trailing Z — frontend sends UTC ISO strings
        start_dt = datetime.fromisoformat(start_date.rstrip('Z'))
        end_dt = datetime.fromisoformat(end_date.rstrip('Z'))

        # The frontend sends UTC; DB stores local time. Shift dates by local offset.
        start_dt = start_dt + local_offset
        end_dt = end_dt + local_offset
        return start_dt, end_dt

    @staticmethod
    def generate_report(template_id: int, start_date: str = None, end_date: str = None):
        try:
            template = ReportTemplate.query.get(template_id)
            if not template:
                return None
            start_dt, end_dt = ReportService._parse_dates(start_date, end_date)
            report_data = {
                'template_name': template.name,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'start_date': start_dt.isoformat(),
                'end_date': end_dt.isoformat(),
                'sections': []
            }
            for section in template.template_config.get('sections', []):
                report_data['sections'].append(
                    ReportService._generate_section(section, start_dt, end_dt)
                )
            return report_data
        except Exception as e:
            logger.error(f"[REPORT] Error generating report: {e}")
            return None

    @staticmethod
    def _generate_section(section_config: dict, start_dt: datetime, end_dt: datetime):
        section_type = section_config.get('type')
        if section_type == 'parameter_stream_summary':
            return ReportService._parameter_stream_summary(section_config, start_dt, end_dt)
        elif section_type == 'parameter_stats':
            return ReportService._parameter_stats(section_config, start_dt, end_dt)
        elif section_type == 'user_summary':
            return ReportService._user_summary(section_config)
        elif section_type == 'activity_log':
            return ReportService._activity_log(section_config, start_dt, end_dt)
        return {'type': section_type, 'data': []}

    @staticmethod
    def _parameter_stream_summary(config: dict, start_dt: datetime, end_dt: datetime):
        try:
            param_id = config.get('parameter_id')
            query = db.session.query(
                ParameterStream.parameter_id,
                func.min(ParameterStream.value).label('min_val'),
                func.max(ParameterStream.value).label('max_val'),
                func.avg(ParameterStream.value).label('avg_val'),
                func.count(ParameterStream.id).label('count'),
                func.max(ParameterStream.timestamp).label('last_seen')
            ).filter(
                ParameterStream.timestamp >= start_dt,
                ParameterStream.timestamp <= end_dt
            )
            if param_id:
                query = query.filter(ParameterStream.parameter_id == param_id)
            rows = query.group_by(ParameterStream.parameter_id).all()
            param_names = {p.id: p.name for p in Parameter.query.all()}
            data = [
                {
                    'parameter_id': r.parameter_id,
                    'parameter_name': param_names.get(r.parameter_id, str(r.parameter_id)),
                    'min': round(r.min_val, 4),
                    'max': round(r.max_val, 4),
                    'avg': round(r.avg_val, 4),
                    'count': r.count,
                    'last_seen': r.last_seen.isoformat() if r.last_seen else None
                }
                for r in rows
            ]
            return {'type': 'parameter_stream_summary', 'title': config.get('title', 'Parameter Stream Summary'), 'data': data}
        except Exception as e:
            logger.error(f"[REPORT] parameter_stream_summary error: {e}")
            return {'type': 'parameter_stream_summary', 'error': str(e)}

    @staticmethod
    def _parameter_stats(config: dict, start_dt: datetime, end_dt: datetime):
        try:
            subq = db.session.query(
                ParameterStream.parameter_id,
                func.max(ParameterStream.timestamp).label('max_ts')
            ).filter(
                ParameterStream.timestamp >= start_dt,
                ParameterStream.timestamp <= end_dt
            ).group_by(ParameterStream.parameter_id).subquery()

            records = db.session.query(ParameterStream).join(
                subq,
                (ParameterStream.parameter_id == subq.c.parameter_id) &
                (ParameterStream.timestamp == subq.c.max_ts)
            ).all()

            param_names = {p.id: {'name': p.name, 'unit': p.unit} for p in Parameter.query.all()}
            data = [
                {
                    'parameter_id': r.parameter_id,
                    'name': param_names.get(r.parameter_id, {}).get('name', str(r.parameter_id)),
                    'unit': param_names.get(r.parameter_id, {}).get('unit', ''),
                    'latest_value': r.value,
                    'timestamp': r.timestamp.isoformat()
                }
                for r in records
            ]
            return {'type': 'parameter_stats', 'title': config.get('title', 'Parameter Statistics'), 'data': data}
        except Exception as e:
            logger.error(f"[REPORT] parameter_stats error: {e}")
            return {'type': 'parameter_stats', 'error': str(e)}

    @staticmethod
    def _user_summary(config: dict):
        try:
            users = User.query.filter_by(is_active=True).all()
            data = [{'user_id': u.id, 'email': u.email, 'name': u.name, 'role': u.role} for u in users]
            return {'type': 'user_summary', 'title': config.get('title', 'User Summary'), 'total': len(data), 'data': data}
        except Exception as e:
            logger.error(f"[REPORT] user_summary error: {e}")
            return {'type': 'user_summary', 'error': str(e)}

    @staticmethod
    def _activity_log(config: dict, start_dt: datetime, end_dt: datetime):
        try:
            from app.models.audit_log import AuditLog
            logs = AuditLog.query.filter(
                AuditLog.created_at >= start_dt,
                AuditLog.created_at <= end_dt
            ).limit(200).all()
            return {'type': 'activity_log', 'title': config.get('title', 'Activity Log'), 'data': [l.to_dict() for l in logs]}
        except Exception as e:
            logger.error(f"[REPORT] activity_log error: {e}")
            return {'type': 'activity_log', 'error': str(e)}

    # ------------------------------------------------------------------
    # Full report: data points + trends + alerts + comparison
    # ------------------------------------------------------------------

    @staticmethod
    def generate_full_report(start_date: str = None, end_date: str = None, limit: int = 500) -> dict:
        start_dt, end_dt = ReportService._parse_dates(start_date, end_date)

        # Only include parameter IDs that exist in the parameters table
        enabled_params = {p.id: {'name': p.name, 'unit': p.unit, 'alert_min': p.alert_min, 'alert_max': p.alert_max}
                         for p in Parameter.query.filter_by(enabled=True).all()}
        if not enabled_params:
            # Fall back to all parameters if none are marked enabled
            enabled_params = {p.id: {'name': p.name, 'unit': p.unit, 'alert_min': p.alert_min, 'alert_max': p.alert_max}
                              for p in Parameter.query.all()}
        enabled_ids = list(enabled_params.keys())

        # --- total count (only enabled parameters) ---
        total_points = db.session.query(func.count(ParameterStream.id)).filter(
            ParameterStream.timestamp >= start_dt,
            ParameterStream.timestamp <= end_dt,
            ParameterStream.parameter_id.in_(enabled_ids)
        ).scalar() or 0

        # --- streamed data points ---
        raw_rows = db.session.query(ParameterStream).filter(
            ParameterStream.timestamp >= start_dt,
            ParameterStream.timestamp <= end_dt,
            ParameterStream.parameter_id.in_(enabled_ids)
        ).order_by(ParameterStream.timestamp.desc()).limit(limit).all()

        data_points = [
            {
                'name': enabled_params.get(r.parameter_id, {}).get('name', str(r.parameter_id)),
                'value': r.value,
                'timestamp': r.timestamp.isoformat(),
                'unit': enabled_params.get(r.parameter_id, {}).get('unit', '')
            }
            for r in raw_rows
        ]

        # --- trends ---
        agg_rows = db.session.query(
            ParameterStream.parameter_id,
            func.min(ParameterStream.value).label('min_val'),
            func.max(ParameterStream.value).label('max_val'),
            func.avg(ParameterStream.value).label('avg_val'),
            func.count(ParameterStream.id).label('count'),
            func.max(ParameterStream.timestamp).label('last_seen')
        ).filter(
            ParameterStream.timestamp >= start_dt,
            ParameterStream.timestamp <= end_dt,
            ParameterStream.parameter_id.in_(enabled_ids)
        ).group_by(ParameterStream.parameter_id).all()

        trends = [
            {
                'parameter_id': r.parameter_id,
                'name': enabled_params.get(r.parameter_id, {}).get('name', str(r.parameter_id)),
                'unit': enabled_params.get(r.parameter_id, {}).get('unit', ''),
                'min': round(r.min_val, 4),
                'max': round(r.max_val, 4),
                'avg': round(r.avg_val, 4),
                'count': r.count,
                'last_seen': r.last_seen.isoformat() if r.last_seen else None
            }
            for r in agg_rows
        ]

        # --- alerts: values outside configured alert_min/alert_max or ±3σ ---
        stats_map = {t['parameter_id']: t for t in trends}
        alerts = []
        for r in raw_rows:
            pinfo = enabled_params.get(r.parameter_id, {})
            pname = pinfo.get('name', str(r.parameter_id))
            alert_min = pinfo.get('alert_min')
            alert_max = pinfo.get('alert_max')
            thresh = ALERT_THRESHOLDS.get(pname)
            reason = None
            # Prefer configured alert_min/alert_max over hardcoded thresholds
            if alert_min is not None and r.value < alert_min:
                reason = f"Below configured min ({alert_min})"
            elif alert_max is not None and r.value > alert_max:
                reason = f"Above configured max ({alert_max})"
            elif thresh:
                if r.value < thresh.get('min', float('-inf')):
                    reason = f"Below min threshold ({thresh['min']})"
                elif r.value > thresh.get('max', float('inf')):
                    reason = f"Above max threshold ({thresh['max']})"
            else:
                st = stats_map.get(r.parameter_id)
                if st and st['count'] > 1:
                    spread = (st['max'] - st['min']) / 4.0 if (st['max'] - st['min']) > 0 else 1
                    if abs(r.value - st['avg']) > 3 * spread:
                        reason = f"Outlier: value {r.value} deviates >3σ from avg {st['avg']}"
            if reason:
                alerts.append({
                    'parameter_id': r.parameter_id,
                    'name': pname,
                    'value': r.value,
                    'timestamp': r.timestamp.isoformat(),
                    'unit': pinfo.get('unit', ''),
                    'reason': reason
                })

        # --- comparison: parameters sorted by avg descending ---
        comparison = sorted(
            [
                {
                    'name': t['name'],
                    'unit': t['unit'],
                    'min': t['min'],
                    'max': t['max'],
                    'avg': t['avg'],
                    'count': t['count']
                }
                for t in trends
            ],
            key=lambda x: x['avg'],
            reverse=True
        )

        return {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'start_date': start_dt.isoformat(),
            'end_date': end_dt.isoformat(),
            'total_data_points': total_points,
            'data_points': data_points,
            'trends': trends,
            'alerts': alerts,
            'comparison': comparison
        }

    # ------------------------------------------------------------------
    # Legacy dashboard report (kept for backward compat)
    # ------------------------------------------------------------------

    @staticmethod
    def generate_dashboard_report(start_date: str = None, end_date: str = None) -> dict:
        start_dt, end_dt = ReportService._parse_dates(start_date, end_date)
        summary = ReportService._parameter_stream_summary({}, start_dt, end_dt)
        stats = ReportService._parameter_stats({}, start_dt, end_dt)
        users = ReportService._user_summary({})
        total_points = db.session.query(func.count(ParameterStream.id)).filter(
            ParameterStream.timestamp >= start_dt,
            ParameterStream.timestamp <= end_dt
        ).scalar() or 0
        return {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'start_date': start_dt.isoformat(),
            'end_date': end_dt.isoformat(),
            'total_data_points': total_points,
            'parameter_summary': summary['data'],
            'latest_values': stats['data'],
            'users': users
        }

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    @staticmethod
    def export_report_json(report_data: dict) -> str:
        return json.dumps(report_data, indent=2, default=str)

    @staticmethod
    def export_full_report_csv(report: dict) -> str:
        """
        CSV export structured like the web UI history page:
        - One section per parameter, each with its own header row
        - Summary section at top
        - Alerts section
        - Comparison section
        """
        output = io.StringIO()
        w = csv.writer(output)

        # ── Header ────────────────────────────────────────────────────────────
        w.writerow(['PrecisionPulse Report'])
        w.writerow(['Generated', report.get('generated_at', '')])
        w.writerow(['Period', f"{report.get('start_date', '')} to {report.get('end_date', '')}"])
        w.writerow(['Total Data Points', report.get('total_data_points', 0)])
        w.writerow([])

        # ── Parameter Summary ─────────────────────────────────────────────────
        trends = report.get('trends', [])
        if trends:
            w.writerow(['=== PARAMETER SUMMARY ==='])
            w.writerow(['Parameter', 'Unit', 'Min', 'Max', 'Avg', 'Readings', 'Last Seen'])
            for t in trends:
                w.writerow([t['name'], t['unit'], t['min'], t['max'], t['avg'],
                             t['count'], (t.get('last_seen') or '')[:19]])
            w.writerow([])

        # ── Per-parameter data sections ───────────────────────────────────────
        # Group data_points by parameter name
        from collections import defaultdict
        by_param: dict = defaultdict(list)
        for dp in report.get('data_points', []):
            by_param[dp['name']].append(dp)

        if by_param:
            w.writerow(['=== DATA POINTS BY PARAMETER ==='])
            w.writerow([])
            for param_name in sorted(by_param.keys()):
                rows = by_param[param_name]
                unit = rows[0].get('unit', '') if rows else ''
                w.writerow([f'--- {param_name} ({unit}) ---'])
                w.writerow(['Timestamp', 'Value', 'Unit'])
                for dp in sorted(rows, key=lambda x: x['timestamp']):
                    w.writerow([dp['timestamp'][:19], dp['value'], dp['unit']])
                w.writerow([])

        # ── Alerts ────────────────────────────────────────────────────────────
        alerts = report.get('alerts', [])
        w.writerow([f'=== ALERTS ({len(alerts)} detected) ==='])
        if alerts:
            w.writerow(['Parameter', 'Value', 'Unit', 'Timestamp', 'Reason'])
            for a in alerts:
                w.writerow([a['name'], a['value'], a['unit'], a['timestamp'][:19], a['reason']])
        else:
            w.writerow(['No alerts detected in this period.'])
        w.writerow([])

        # ── Comparison ────────────────────────────────────────────────────────
        comparison = report.get('comparison', [])
        if comparison:
            w.writerow(['=== PARAMETER COMPARISON (sorted by avg) ==='])
            w.writerow(['Rank', 'Parameter', 'Unit', 'Min', 'Max', 'Avg', 'Readings'])
            for i, c in enumerate(comparison, 1):
                w.writerow([i, c['name'], c['unit'], c['min'], c['max'], c['avg'], c['count']])
            w.writerow([])

        return output.getvalue()

    @staticmethod
    def _build_line_chart_drawing(series_data: list, title: str, width: float = 480, height: float = 200):
        """
        Build a reportlab Drawing containing a multi-line chart.
        series_data: list of {'name': str, 'points': [(x_float, y_float), ...]}
        Returns a Drawing object ready to add to a platypus story.
        """
        from reportlab.graphics.shapes import Drawing, String, Rect, Line
        from reportlab.graphics.charts.lineplots import LinePlot
        from reportlab.lib import colors as rl_colors

        COLORS = [
            rl_colors.HexColor('#6366f1'), rl_colors.HexColor('#22d3ee'),
            rl_colors.HexColor('#f59e0b'), rl_colors.HexColor('#10b981'),
            rl_colors.HexColor('#f43f5e'), rl_colors.HexColor('#a78bfa'),
            rl_colors.HexColor('#34d399'), rl_colors.HexColor('#fb923c'),
        ]

        d = Drawing(width, height)

        # Dark background
        d.add(Rect(0, 0, width, height, fillColor=rl_colors.HexColor('#1e293b'),
                   strokeColor=rl_colors.HexColor('#334155'), strokeWidth=1))

        # Title
        if title:
            d.add(String(width / 2, height - 14, title,
                         fontSize=9, fillColor=rl_colors.HexColor('#e2e8f0'),
                         textAnchor='middle'))

        # Filter series with data
        valid = [s for s in series_data if s.get('points')]
        if not valid:
            d.add(String(width / 2, height / 2, 'No data',
                         fontSize=9, fillColor=rl_colors.HexColor('#64748b'),
                         textAnchor='middle'))
            return d

        lp = LinePlot()
        lp.x = 55
        lp.y = 35
        lp.width = width - 75
        lp.height = height - (60 if title else 50)

        all_x, all_y = [], []
        lp.data = []
        for s in valid:
            pts = s['points']
            lp.data.append(pts)
            all_x.extend(p[0] for p in pts)
            all_y.extend(p[1] for p in pts)

        if all_x and all_y:
            x_min, x_max = min(all_x), max(all_x)
            y_min, y_max = min(all_y), max(all_y)
            x_pad = (x_max - x_min) * 0.02 or 1
            y_pad = (y_max - y_min) * 0.1 or abs(y_max) * 0.05 or 1
            lp.xValueAxis.valueMin = x_min - x_pad
            lp.xValueAxis.valueMax = x_max + x_pad
            lp.yValueAxis.valueMin = y_min - y_pad
            lp.yValueAxis.valueMax = y_max + y_pad

        lp.xValueAxis.labelTextFormat = ''
        lp.xValueAxis.strokeColor = rl_colors.HexColor('#475569')
        lp.xValueAxis.gridStrokeColor = rl_colors.HexColor('#1e293b')
        lp.yValueAxis.strokeColor = rl_colors.HexColor('#475569')
        lp.yValueAxis.gridStrokeColor = rl_colors.HexColor('#334155')
        lp.yValueAxis.gridStrokeDashArray = [2, 2]
        lp.yValueAxis.visibleGrid = True
        lp.xValueAxis.labels.fontSize = 7
        lp.xValueAxis.labels.fillColor = rl_colors.HexColor('#64748b')
        lp.yValueAxis.labels.fontSize = 7
        lp.yValueAxis.labels.fillColor = rl_colors.HexColor('#64748b')

        for i, s in enumerate(valid):
            c = COLORS[i % len(COLORS)]
            lp.lines[i].strokeColor = c
            lp.lines[i].strokeWidth = 1.5

        d.add(lp)

        # Legend at bottom
        from reportlab.graphics.shapes import Rect as RRect
        legend_x = 56
        legend_y = 10
        for i, s in enumerate(valid):
            c = COLORS[i % len(COLORS)]
            d.add(RRect(legend_x, legend_y, 12, 4, fillColor=c, strokeColor=c))
            d.add(String(legend_x + 15, legend_y + 1, s.get('name', ''),
                         fontSize=6.5, fillColor=rl_colors.HexColor('#94a3b8')))
            legend_x += min(90, len(s.get('name', '')) * 5.5 + 22)
            if legend_x > width - 70:
                break

        return d

    @staticmethod
    def _series_from_report(report: dict):
        """
        Build per-parameter time-series from report data_points.
        Returns list of {'name': str, 'unit': str, 'points': [(epoch_float, value), ...]}
        """
        from collections import defaultdict
        grouped = defaultdict(list)
        for dp in report.get('data_points', []):
            try:
                ts = datetime.fromisoformat(dp['timestamp'].rstrip('Z'))
                epoch = ts.timestamp()
                grouped[dp['name']].append((epoch, float(dp['value'])))
            except Exception:
                continue
        result = []
        for name, pts in grouped.items():
            pts.sort(key=lambda p: p[0])
            result.append({'name': name, 'points': pts})
        return result

    @staticmethod
    def export_full_report_pdf(report: dict) -> bytes:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
            PageBreak, KeepTogether,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm

        output = io.BytesIO()
        doc = SimpleDocTemplate(
            output, pagesize=landscape(A4),
            leftMargin=18*mm, rightMargin=18*mm,
            topMargin=14*mm, bottomMargin=14*mm,
        )
        PAGE_W = landscape(A4)[0] - 36*mm   # usable width

        styles = getSampleStyleSheet()
        title_style  = ParagraphStyle('RPTitle',  fontSize=18, textColor=colors.HexColor('#4F46E5'), spaceAfter=4, alignment=1)
        sub_style    = ParagraphStyle('RPSub',    fontSize=10, textColor=colors.HexColor('#64748b'), spaceAfter=2, alignment=1)
        section_style= ParagraphStyle('RPSect',   fontSize=11, textColor=colors.white,
                                      backColor=colors.HexColor('#1e293b'), spaceBefore=8, spaceAfter=4,
                                      leftIndent=4, rightIndent=4, leading=16)
        normal       = styles['Normal']
        normal.fontSize = 8

        header_ts = TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
            ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, -1), 7.5),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#F1F5F9')]),
            ('GRID',         (0, 0), (-1, -1), 0.3, colors.HexColor('#CBD5E1')),
            ('TOPPADDING',   (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
            ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ])
        alert_ts = TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.HexColor('#DC2626')),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
            ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, -1), 7.5),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#FEF2F2'), colors.white]),
            ('GRID',         (0, 0), (-1, -1), 0.3, colors.HexColor('#FECACA')),
            ('TOPPADDING',   (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
            ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ])

        elements = []

        # ── Cover ──────────────────────────────────────────────────────────────
        elements.append(Spacer(1, 20*mm))
        elements.append(Paragraph('PrecisionPulse', title_style))
        elements.append(Paragraph('Telemetry Parameter Report', sub_style))
        elements.append(Paragraph(f"Period: {report.get('start_date', '')[:10]}  →  {report.get('end_date', '')[:10]}", sub_style))
        elements.append(Paragraph(f"Generated: {report.get('generated_at', '')}", sub_style))
        elements.append(Paragraph(f"Total Data Points: {report.get('total_data_points', 0):,}", sub_style))
        elements.append(Spacer(1, 8*mm))

        # ── Summary table ──────────────────────────────────────────────────────
        trends = report.get('trends', [])
        if trends:
            elements.append(Paragraph('Parameter Summary', section_style))
            col_w = [PAGE_W*0.30, PAGE_W*0.08, PAGE_W*0.13, PAGE_W*0.13, PAGE_W*0.13, PAGE_W*0.12, PAGE_W*0.11]
            tdata = [['Parameter', 'Unit', 'Min', 'Max', 'Avg', 'Readings', 'Last Seen']]
            for t in trends:
                ls = t.get('last_seen', '') or ''
                tdata.append([t['name'], t['unit'], t['min'], t['max'], t['avg'],
                               t['count'], ls[:19]])
            tbl = Table(tdata, colWidths=col_w)
            tbl.setStyle(header_ts)
            elements.append(tbl)
            elements.append(Spacer(1, 6*mm))

        # ── Alerts table ───────────────────────────────────────────────────────
        alerts = report.get('alerts', [])
        elements.append(Paragraph(f'Alerts ({len(alerts)} detected)', section_style))
        if alerts:
            col_w = [PAGE_W*0.18, PAGE_W*0.08, PAGE_W*0.07, PAGE_W*0.22, PAGE_W*0.45]
            adata = [['Parameter', 'Value', 'Unit', 'Timestamp', 'Reason']]
            for a in alerts[:100]:
                adata.append([a['name'], a['value'], a['unit'], a['timestamp'][:19], a['reason']])
            tbl = Table(adata, colWidths=col_w)
            tbl.setStyle(alert_ts)
            elements.append(tbl)
        else:
            elements.append(Paragraph('No alerts detected in this period.', normal))
        elements.append(Spacer(1, 6*mm))

        # ── Comparison table ───────────────────────────────────────────────────
        comparison = report.get('comparison', [])
        if comparison:
            elements.append(Paragraph('Parameter Comparison (sorted by avg)', section_style))
            col_w = [PAGE_W*0.30, PAGE_W*0.10, PAGE_W*0.15, PAGE_W*0.15, PAGE_W*0.15, PAGE_W*0.15]
            cdata = [['Parameter', 'Unit', 'Min', 'Max', 'Avg', 'Readings']]
            for c in comparison:
                cdata.append([c['name'], c['unit'], c['min'], c['max'], c['avg'], c['count']])
            tbl = Table(cdata, colWidths=col_w)
            tbl.setStyle(header_ts)
            elements.append(tbl)
            elements.append(Spacer(1, 6*mm))

        # ── Data points table (capped at 200) ──────────────────────────────────
        dp_list = report.get('data_points', [])[:200]
        if dp_list:
            elements.append(PageBreak())
            elements.append(Paragraph(
                f'Data Points (showing {len(dp_list)} of {report.get("total_data_points", 0):,})',
                section_style))
            col_w = [PAGE_W*0.28, PAGE_W*0.12, PAGE_W*0.10, PAGE_W*0.50]
            dpdata = [['Parameter', 'Value', 'Unit', 'Timestamp']]
            for d in dp_list:
                dpdata.append([d['name'], d['value'], d['unit'], d['timestamp'][:19]])
            tbl = Table(dpdata, colWidths=col_w)
            tbl.setStyle(header_ts)
            elements.append(tbl)

        # ── Charts ─────────────────────────────────────────────────────────────
        series_all = ReportService._series_from_report(report)
        if series_all:
            elements.append(PageBreak())
            elements.append(Paragraph('Multi-Parameter Line Chart (All Parameters)', section_style))
            elements.append(Spacer(1, 3*mm))
            try:
                chart_w = PAGE_W
                chart_h = min(200, max(120, 30 * len(series_all)))
                drawing = ReportService._build_line_chart_drawing(
                    series_all, '', width=float(chart_w), height=float(chart_h)
                )
                elements.append(drawing)
            except Exception as chart_err:
                logger.warning('[REPORT] Combined chart error: %s', chart_err)
            elements.append(Spacer(1, 6*mm))

            # Individual chart per parameter
            elements.append(Paragraph('Individual Parameter Charts', section_style))
            elements.append(Spacer(1, 3*mm))
            for s in series_all:
                if len(s['points']) < 2:
                    continue
                try:
                    drawing = ReportService._build_line_chart_drawing(
                        [s], s['name'], width=float(PAGE_W), height=160.0
                    )
                    elements.append(KeepTogether([drawing, Spacer(1, 4*mm)]))
                except Exception as chart_err:
                    logger.warning('[REPORT] Chart error for %s: %s', s['name'], chart_err)

        doc.build(elements)
        output.seek(0)
        return output.read()

    @staticmethod
    def export_report_csv(report_data: dict) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Report', report_data.get('template_name', 'Dashboard Report')])
        writer.writerow(['Generated', report_data.get('generated_at')])
        writer.writerow(['Period', f"{report_data.get('start_date')} to {report_data.get('end_date')}"])
        writer.writerow([])
        for section in report_data.get('sections', []):
            writer.writerow([section.get('title', section.get('type'))])
            data = section.get('data', [])
            if data and isinstance(data[0], dict):
                writer.writerow(list(data[0].keys()))
                for row in data:
                    writer.writerow(list(row.values()))
            writer.writerow([])
        for key in ['parameter_summary', 'latest_values']:
            rows = report_data.get(key, [])
            if rows:
                writer.writerow([key.replace('_', ' ').title()])
                writer.writerow(list(rows[0].keys()))
                for row in rows:
                    writer.writerow(list(row.values()))
                writer.writerow([])
        return output.getvalue()


report_service = ReportService()
