from flask import Blueprint, request, jsonify, send_file
from app.middleware.auth_middleware import token_required
from app.models.parameter_stream import ParameterStream
from app.models.parameter import Parameter
from app.models import db
from datetime import datetime, timedelta
from sqlalchemy import desc
import logging
import io

logger = logging.getLogger(__name__)

history_export_bp = Blueprint('history_export', __name__, url_prefix='/api/reports/history')

@history_export_bp.route('/export/pdf', methods=['GET'])
@token_required
def export_history_pdf():
    """Export parameter history as PDF with charts and statistics"""
    try:
        preset = request.args.get('preset', 'last_24_hours')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        param_ids = request.args.getlist('param_ids', type=int)
        
        now = datetime.now()
        
        if preset == 'last_15_minutes':
            start_time = now - timedelta(minutes=15)
        elif preset == 'last_30_minutes':
            start_time = now - timedelta(minutes=30)
        elif preset == 'last_hour':
            start_time = now - timedelta(hours=1)
        elif preset == 'last_6_hours':
            start_time = now - timedelta(hours=6)
        elif preset == 'last_24_hours':
            start_time = now - timedelta(days=1)
        elif preset == 'last_7_days':
            start_time = now - timedelta(days=7)
        elif preset == 'last_30_days':
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(hours=1)
        
        if preset == 'custom' and start_date_str:
            try:
                start_time = datetime.fromisoformat(start_date_str.replace('Z', '+00:00')).replace(tzinfo=None)
            except (ValueError, TypeError):
                start_time = now - timedelta(hours=1)
        
        end_time = now
        if end_date_str:
            try:
                end_time = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')).replace(tzinfo=None)
            except (ValueError, TypeError):
                end_time = now
        
        query = db.session.query(ParameterStream).filter(
            ParameterStream.timestamp >= start_time,
            ParameterStream.timestamp <= end_time
        )
        
        if param_ids:
            query = query.filter(ParameterStream.parameter_id.in_(param_ids))
        
        records = query.order_by(desc(ParameterStream.timestamp)).limit(2000).all()
        
        param_names = {p.id: {'name': p.name, 'unit': p.unit} for p in Parameter.query.all()}
        
        grouped = {}
        for r in records:
            pid = r.parameter_id
            if pid not in grouped:
                grouped[pid] = {
                    'parameter_id': pid,
                    'name': param_names.get(pid, {}).get('name', str(pid)),
                    'unit': param_names.get(pid, {}).get('unit', ''),
                    'data': []
                }
            grouped[pid]['data'].append({'timestamp': r.timestamp.isoformat(), 'value': r.value})
        
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')
            import statistics as stats_module
            
            pdf_buffer = io.BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
            story = []
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1e293b'),
                spaceAfter=6,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor('#64748b'),
                spaceAfter=12,
                alignment=TA_CENTER
            )
            
            story.append(Paragraph('PrecisionPulse — Parameter History Report', title_style))
            story.append(Paragraph(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | Range: {preset}', subtitle_style))
            story.append(Spacer(1, 0.2*inch))
            
            for param_id, param_data in sorted(grouped.items()):
                story.append(Paragraph(f"{param_data['name']} ({param_data['unit']})", styles['Heading2']))
                
                values = [d['value'] for d in param_data['data']]
                if values:
                    stats_data = [
                        ['Metric', 'Value'],
                        ['Records', str(len(values))],
                        ['Min', f"{min(values):.2f}"],
                        ['Max', f"{max(values):.2f}"],
                        ['Average', f"{sum(values)/len(values):.2f}"],
                        ['Std Dev', f"{stats_module.stdev(values) if len(values) > 1 else 0:.2f}"]
                    ]
                    
                    stats_table = Table(stats_data, colWidths=[2*inch, 2*inch])
                    stats_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f1f5f9')),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
                    ]))
                    story.append(stats_table)
                    story.append(Spacer(1, 0.15*inch))
                    
                    try:
                        fig, ax = plt.subplots(figsize=(7, 3), dpi=100)
                        ax.plot(range(len(values)), values, color='#3b82f6', linewidth=2, marker='o', markersize=3)
                        ax.fill_between(range(len(values)), values, alpha=0.2, color='#3b82f6')
                        ax.set_xlabel('Time', fontsize=9, color='#64748b')
                        ax.set_ylabel(f"Value ({param_data['unit']})", fontsize=9, color='#64748b')
                        ax.set_title(f"{param_data['name']} Trend", fontsize=11, fontweight='bold', color='#1e293b')
                        ax.grid(True, alpha=0.2, color='#cbd5e1')
                        ax.set_facecolor('#f8fafc')
                        fig.patch.set_facecolor('white')
                        plt.tight_layout()
                        
                        img_buffer = io.BytesIO()
                        fig.savefig(img_buffer, format='png', dpi=100, bbox_inches='tight')
                        img_buffer.seek(0)
                        plt.close(fig)
                        
                        img = Image(img_buffer, width=6.5*inch, height=2.5*inch)
                        story.append(img)
                    except Exception as e:
                        logger.error(f"[REPORT] Chart generation failed: {e}")
                    
                    story.append(Spacer(1, 0.3*inch))
                    story.append(PageBreak())
            
            doc.build(story)
            pdf_buffer.seek(0)
            
            return send_file(
                pdf_buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'history_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            )
        except ImportError as ie:
            logger.error(f"[REPORT] Missing dependency: {ie}")
            return jsonify({'error': 'PDF generation not available - missing reportlab or matplotlib'}), 500
    
    except Exception as e:
        logger.error(f"[REPORT] Error exporting history PDF: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
