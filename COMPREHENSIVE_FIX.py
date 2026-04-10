"""
COMPREHENSIVE FIX FOR USER SYNC AND PDF EXPORT
This file contains all the fixes needed for:
1. User sync to work properly (SQLite + PostgreSQL)
2. PDF export with full history page content
"""

# ============================================================================
# PART 1: FIX FOR BACKEND USER SYNC ENDPOINTS
# File: dspl-precision-pulse-backend/app/routes/internal_routes.py
# ============================================================================

# REPLACE the sync_user function with this:

@internal_bp.route('/sync-user', methods=['POST'])
def sync_user():
    """
    Sync user from desktop to backend (create or update)
    Properly updates role and broadcasts changes
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        email = data.get('email')
        name = data.get('name')
        password_hash = data.get('password_hash')
        role = data.get('role', 'user')
        is_active = data.get('is_active', True)

        if not email or not name:
            return jsonify({'error': 'Email and name required'}), 400

        user = User.query.filter_by(email=email).first()
        if user:
            # UPDATE existing user
            old_role = user.role
            user.name = name
            user.role = role
            user.is_active = is_active
            if password_hash and password_hash.strip():
                user.password_hash = password_hash
            user.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(f"[SYNC] User UPDATED: {email} (role: {old_role} → {role})")
            
            # Broadcast role change if changed
            if old_role != role:
                try:
                    publisher = get_mqtt_publisher()
                    if publisher:
                        payload = {
                            'type': 'role_changed',
                            'email': email,
                            'old_role': old_role,
                            'new_role': role,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                        publisher._publish('precisionpulse/sync/roles/changed', payload)
                        logger.info(f"[SYNC] MQTT broadcast: role_changed for {email}")
                except Exception as mqtt_err:
                    logger.warning(f"[SYNC] MQTT broadcast failed: {mqtt_err}")
            
            return jsonify({
                'success': True,
                'message': 'User updated',
                'user': user.to_dict()
            }), 200
        else:
            # CREATE new user
            user = User(
                email=email,
                name=name,
                password_hash=password_hash or '',
                role=role,
                is_active=is_active
            )
            db.session.add(user)
            db.session.commit()
            logger.info(f"[SYNC] User CREATED: {email} (role={role})")
            
            # Broadcast creation
            try:
                publisher = get_mqtt_publisher()
                if publisher:
                    payload = {
                        'type': 'user_created',
                        'user': user.to_dict(),
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    publisher._publish('precisionpulse/sync/users/created', payload)
                    logger.info(f"[SYNC] MQTT broadcast: user_created for {email}")
            except Exception as mqtt_err:
                logger.warning(f"[SYNC] MQTT broadcast failed: {mqtt_err}")
            
            return jsonify({
                'success': True,
                'message': 'User created',
                'user': user.to_dict()
            }), 201
    except Exception as e:
        logger.error(f"[SYNC] Error syncing user: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# PART 2: COMPREHENSIVE PDF EXPORT WITH FULL HISTORY PAGE CONTENT
# File: dspl-precision-pulse-backend/app/routes/history_export_routes.py
# ============================================================================

from flask import Blueprint, request, jsonify, send_file
from app.middleware.auth_middleware import token_required
from app.models.parameter_stream import ParameterStream
from app.models.parameter import Parameter
from app.models import db
from datetime import datetime, timedelta
from sqlalchemy import desc, func
import logging
import io
import statistics as stats_module

logger = logging.getLogger(__name__)

history_export_bp = Blueprint('history_export', __name__, url_prefix='/api/reports/history')

@history_export_bp.route('/export/pdf', methods=['GET'])
@token_required
def export_history_pdf():
    """
    Export parameter history as PDF with FULL HISTORY PAGE CONTENT
    Includes: charts, statistics, table, search, filters - everything from history page
    """
    try:
        preset = request.args.get('preset', 'last_24_hours')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        param_ids = request.args.getlist('param_ids', type=int)
        
        now = datetime.now()
        
        # Calculate time range based on preset
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
        
        # Handle custom date range
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
        
        # Query telemetry data
        query = db.session.query(ParameterStream).filter(
            ParameterStream.timestamp >= start_time,
            ParameterStream.timestamp <= end_time
        )
        
        if param_ids:
            query = query.filter(ParameterStream.parameter_id.in_(param_ids))
        
        records = query.order_by(desc(ParameterStream.timestamp)).limit(2000).all()
        
        # Get parameter metadata
        param_names = {p.id: {'name': p.name, 'unit': p.unit} for p in Parameter.query.all()}
        
        # Group records by parameter
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
            grouped[pid]['data'].append({
                'timestamp': r.timestamp.isoformat(),
                'value': r.value
            })
        
        # Generate PDF with reportlab and matplotlib
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')
            
            pdf_buffer = io.BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
            story = []
            styles = getSampleStyleSheet()
            
            # Custom styles
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
            
            param_title_style = ParagraphStyle(
                'ParamTitle',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor('#1e293b'),
                spaceAfter=10,
                fontName='Helvetica-Bold'
            )
            
            # Header
            story.append(Paragraph('PrecisionPulse — Parameter History Report', title_style))
            story.append(Paragraph(
                f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | Range: {preset} | Parameters: {len(grouped)}',
                subtitle_style
            ))
            story.append(Spacer(1, 0.2*inch))
            
            # Summary statistics
            all_values = []
            for param_data in grouped.values():
                all_values.extend([d['value'] for d in param_data['data']])
            
            if all_values:
                summary_data = [
                    ['Metric', 'Value'],
                    ['Total Records', str(len(all_values))],
                    ['Min Value', f"{min(all_values):.2f}"],
                    ['Max Value', f"{max(all_values):.2f}"],
                    ['Average', f"{sum(all_values)/len(all_values):.2f}"],
                    ['Std Dev', f"{stats_module.stdev(all_values) if len(all_values) > 1 else 0:.2f}"]
                ]
                
                summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
                summary_table.setStyle(TableStyle([
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
                story.append(Paragraph('Summary Statistics', styles['Heading3']))
                story.append(summary_table)
                story.append(Spacer(1, 0.3*inch))
            
            # Per-parameter details
            for param_id, param_data in sorted(grouped.items()):
                story.append(Paragraph(f"{param_data['name']} ({param_data['unit']})", param_title_style))
                
                values = [d['value'] for d in param_data['data']]
                if values:
                    # Statistics table
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
                        ('FONTSIZE', (0, 0), (-1, 0), 9),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f1f5f9')),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
                    ]))
                    story.append(stats_table)
                    story.append(Spacer(1, 0.15*inch))
                    
                    # Trend chart
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
                    
                    story.append(Spacer(1, 0.15*inch))
                    
                    # Data table (last 20 records)
                    table_data = [['Timestamp', f'Value ({param_data["unit"]})']
                    for record in param_data['data'][:20]:
                        ts = datetime.fromisoformat(record['timestamp'])
                        ts_str = ts.strftime('%Y-%m-%d %H:%M:%S')
                        table_data.append([ts_str, f"{record['value']:.2f}"])
                    
                    data_table = Table(table_data, colWidths=[3.5*inch, 2.5*inch])
                    data_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 9),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f1f5f9')),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
                    ]))
                    story.append(Paragraph('Latest 20 Records', styles['Heading4']))
                    story.append(data_table)
                    story.append(Spacer(1, 0.3*inch))
                    story.append(PageBreak())
            
            # Build PDF
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
            return jsonify({'error': 'PDF generation not available - install reportlab and matplotlib'}), 500
    
    except Exception as e:
        logger.error(f"[REPORT] Error exporting history PDF: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ============================================================================
# PART 3: DESKTOP APP FIX - ENSURE PROPER SYNC
# File: dspl-precision-pulse-desktop/src/ui/manage_users_page.py
# ============================================================================

# In the edit_user method, REPLACE with this:

def edit_user(self, index):
    """Edit user - properly sync role changes"""
    user = self.users[index]
    dialog = EditUserDialog(self, user)
    if dialog.exec():
        user_data = dialog.get_user_data()
        if self.db:
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                # UPDATE user role in SQLite
                cursor.execute('''
                    UPDATE users SET role = ?, name = ?, is_active = ?,
                    updated_at = datetime('now','localtime')
                    WHERE id = ?
                ''', (user_data['role'], user_data['name'], 
                      1 if user_data['is_active'] else 0, user['id']))
                conn.commit()
                logger.info(f"[DESKTOP] Updated user {user['email']} role to {user_data['role']} in SQLite")
            
            # Sync to backend PostgreSQL
            try:
                import requests
                response = requests.put(
                    f"http://localhost:5000/api/internal/sync-user-role",
                    json={"email": user['email'], "role": user_data['role']},
                    headers={"Content-Type": "application/json"},
                    timeout=5
                )
                if response.status_code == 200:
                    logger.info(f"✓ User role synced to backend: {user['email']} → {user_data['role']}")
                else:
                    logger.error(f"✗ Backend sync failed: {response.status_code}")
            except Exception as e:
                logger.error(f"✗ Backend sync error: {e}")
            
            # Publish to MQTT
            if self.sync_service:
                self.sync_service.publish_user_change('update', {
                    'email': user['email'],
                    'name': user_data['name'],
                    'role': user_data['role'],
                    'is_active': user_data['is_active']
                })
                logger.info(f"[MQTT] Published user update: {user['email']}")
            
            msg = CustomMessageBox("Success", "User updated successfully")
            msg.exec()
            self.refresh_table()


# ============================================================================
# PART 4: INSTALLATION & DEPLOYMENT
# ============================================================================

"""
INSTALLATION STEPS:

1. Install dependencies:
   cd dspl-precision-pulse-backend
   pip install reportlab matplotlib

2. Apply the fixes:
   - Replace sync_user function in app/routes/internal_routes.py
   - Replace history_export_routes.py with new comprehensive version
   - Update edit_user method in desktop manage_users_page.py

3. Restart backend:
   python run.py

4. Test user sync:
   curl -X PUT http://localhost:5000/api/internal/sync-user-role \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","role":"admin"}'

5. Test PDF export:
   curl -X GET "http://localhost:5000/api/reports/history/export/pdf?preset=last_24_hours&param_ids=1" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -o history.pdf

VERIFICATION:

1. Check SQLite:
   sqlite3 dspl-precision-pulse-desktop/data/precision_pulse.db
   SELECT * FROM users WHERE email='test@example.com';

2. Check PostgreSQL:
   psql -U postgres -d precision_pulse
   SELECT * FROM users WHERE email='test@example.com';

3. Check MQTT:
   mosquitto_sub -h localhost -p 18883 -t "precisionpulse/sync/#" --cafile config/ca.crt

4. Check logs:
   tail -f dspl-precision-pulse-backend/app.log | grep "\[SYNC\]"
   tail -f dspl-precision-pulse-desktop/app.log | grep "\[DESKTOP\]"
"""
