"""
Parameters page for telemetry configuration
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QFrame, QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QCheckBox, QDialog, QLineEdit, QTextEdit)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap
from typing import Dict
import os

from src.ui.CustomMessageBox import CustomMessageBox1
from src.ui.CustomMessageBox import CustomMessageBox


class ParametersPage(QWidget):
    """Full-page parameters configuration"""
    
    back_clicked = Signal()
    parameters_changed = Signal()
    
    def __init__(self, db_manager=None, auth_service=None, sync_service=None, parameter_sync_service=None):
        super().__init__()
        self.db = db_manager
        self.auth_service = auth_service
        self.sync_service = sync_service
        self.parameter_sync_service = parameter_sync_service
        self.parameters = self.get_default_parameters()
        self._info_label = None   # kept as instance ref so we can update it
        self._table_container_layout = None  # layout that owns the table
        self.setup_ui()
        if parameter_sync_service:
            parameter_sync_service.parameters_fetched.connect(self._on_parameters_fetched)
            parameter_sync_service.parameter_updated.connect(self._on_parameter_updated)
    
    def setup_ui(self):
        """Setup parameters page UI"""
        self.setStyleSheet("background-color: #1e293b;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        self.create_header(layout)
        
        # Content
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #1e293b;")
        content_layout = QVBoxLayout(content_widget)
        
        # Responsive margins and spacing
        screen_width = self.screen().availableGeometry().width()
        margin = 20 if screen_width < 1200 else 40
        spacing = 15 if screen_width < 1200 else 30
        
        content_layout.setContentsMargins(margin, margin, margin, margin)
        content_layout.setSpacing(spacing)
        
        # Title section
        title_layout = QHBoxLayout()
        
        title_section = QVBoxLayout()
        title_label = QLabel("Telemetry Parameters")
        title_label.setStyleSheet("font-size: 36px; font-weight: 700; color: white;")
        
        subtitle_label = QLabel("Configure which parameters the desktop application should collect")
        subtitle_label.setStyleSheet("font-size: 16px; color: #94a3b8;")
        
        title_section.addWidget(title_label)
        title_section.addWidget(subtitle_label)
        
        title_layout.addLayout(title_section)
        title_layout.addStretch()
        
        # Action buttons (admin can add parameters)
        if self.auth_service:
            user = self.auth_service.get_current_user()
            if user and user.get('role') == 'admin':
                add_btn = QPushButton("+ Add Parameter")
                add_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #059669;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 12px 24px;
                        font-weight: 600;
                        font-size: 14px;
                    }
                    QPushButton:hover { background-color: #047857; }
                """)
                add_btn.clicked.connect(self.add_parameter)
                title_layout.addWidget(add_btn)
        
        content_layout.addLayout(title_layout)
        
        # Info box
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #1e3a5f;
                border: 1px solid #3b82f6;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        info_layout = QHBoxLayout(info_frame)
        self._info_label = QLabel(self._info_text())
        self._info_label.setStyleSheet("color: #93c5fd; font-size: 14px;")
        info_layout.addWidget(self._info_label)
        content_layout.addWidget(info_frame)
        
        # Parameters table — store the layout so we can swap the table later
        self._table_container_layout = content_layout
        self.create_table(content_layout)
        
        layout.addWidget(content_widget)
    
    def create_header(self, layout):
        """Create header section"""
        header_frame = QFrame()
        header_frame.setFixedHeight(90)
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #2d3748;
                border: none;
            }
        """)
        
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(30, 0, 30, 0)
        
        # Logo and title
        logo_title_layout = QHBoxLayout()
        logo_title_layout.setSpacing(15)
        
        # Logo
        logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'logo.svg')
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(pixmap.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_label.setStyleSheet("background-color: transparent;")
        else:
            logo_label.setText("⚡")
            logo_label.setStyleSheet("""
                QLabel {
                    background-color: #2563eb;
                    color: white;
                    font-size: 28px;
                    border-radius: 12px;
                    padding: 8px;
                }
            """)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setFixedSize(50, 50)
        
        # Title
        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)
        
        title_label = QLabel("PrecisionPulse")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 22px;
                font-weight: 700;
                background: transparent;
            }
        """)
        
        subtitle_label = QLabel("Parameter Configuration")
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #94a3b8;
                font-size: 14px;
                background: transparent;
            }
        """)
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        
        logo_title_layout.addWidget(logo_label)
        logo_title_layout.addLayout(title_layout)
        
        header_layout.addLayout(logo_title_layout)
        header_layout.addStretch()
        
        # Back button
        back_btn = QPushButton("Back to Dashboard")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #1e293b;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #f1f5f9; }
        """)
        back_btn.clicked.connect(self.back_clicked.emit)
        
        header_layout.addWidget(back_btn)
        layout.addWidget(header_frame)
    
    def create_table(self, layout):
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Status", "Parameter", "Unit", "Alert Range", "Description", "Actions"])
        table.setStyleSheet("""
            QTableWidget {
                background-color: #2d3748;
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                selection-background-color: #1e3a5f;
            }
            QTableWidget::item {
                padding: 16px;
                border-bottom: 1px solid #374151;
            }
            QTableWidget::item:selected {
                background-color: #1e3a5f;
            }
            QHeaderView::section {
                background-color: #374151;
                color: #9ca3af;
                padding: 16px;
                border: none;
                font-weight: 600;
                font-size: 13px;
                text-transform: uppercase;
            }
        """)
        
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        
        table.setColumnWidth(0, 150)
        table.setColumnWidth(2, 100)
        table.setColumnWidth(3, 140)
        table.setColumnWidth(5, 200)
        
        table.verticalHeader().setVisible(False)
        table.setRowCount(len(self.parameters))
        table.setSelectionBehavior(QTableWidget.SelectRows)
        
        for i, param in enumerate(self.parameters):
            # Status - clickable button
            status_widget = QWidget()
            status_widget.setStyleSheet("background: transparent;")
            status_layout = QHBoxLayout(status_widget)
            status_layout.setContentsMargins(16, 0, 0, 0)
            
            status_btn = QPushButton(f"{'✓' if param['enabled'] else '✗'} {'Enabled' if param['enabled'] else 'Disabled'}")
            status_btn.setProperty('param_index', i)
            status_btn.setCursor(Qt.PointingHandCursor)
            status_btn.setStyleSheet(f"""
                QPushButton {{
                    color: white;
                    background-color: {'#059669' if param['enabled'] else '#dc2626'};
                    padding: 6px 12px;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 12px;
                    border: none;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {'#047857' if param['enabled'] else '#b91c1c'};
                }}
            """)
            status_btn.clicked.connect(lambda checked, idx=i: self.toggle_parameter(idx))
            
            status_layout.addWidget(status_btn)
            status_layout.addStretch()
            table.setCellWidget(i, 0, status_widget)
            
            # Parameter
            param_item = QTableWidgetItem(param['name'])
            param_item.setFlags(param_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(i, 1, param_item)
            
            # Unit
            unit_item = QTableWidgetItem(param['unit'])
            unit_item.setFlags(unit_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(i, 2, unit_item)
            
            # Alert Range
            alert_min = param.get('alert_min')
            alert_max = param.get('alert_max')
            if alert_min is not None and alert_max is not None:
                range_text = f"{alert_min} – {alert_max}"
            elif alert_min is not None:
                range_text = f"≥ {alert_min}"
            elif alert_max is not None:
                range_text = f"≤ {alert_max}"
            else:
                range_text = "Not set"
            range_item = QTableWidgetItem(range_text)
            range_item.setFlags(range_item.flags() & ~Qt.ItemIsEditable)
            range_item.setForeground(Qt.cyan if (alert_min is not None or alert_max is not None) else Qt.gray)
            table.setItem(i, 3, range_item)
            
            # Description
            desc_item = QTableWidgetItem(param['description'])
            desc_item.setForeground(Qt.gray)
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemIsEditable)
            table.setItem(i, 4, desc_item)
            
            # Actions
            actions_widget = QWidget()
            actions_widget.setStyleSheet("background: transparent;")
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 16, 0)
            actions_layout.addStretch()
            
            # Alert config button (all users can set alert range)
            alert_btn = QPushButton("Set Alert")
            alert_btn.setStyleSheet("""
                QPushButton {
                    background-color: #7c3aed;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-weight: 600;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #6d28d9; }
            """)
            alert_btn.clicked.connect(lambda checked, idx=i: self.set_alert_range(idx))
            actions_layout.addWidget(alert_btn)
            
            # Only show remove button for admins
            if self.auth_service:
                user = self.auth_service.get_current_user()
                if user and user.get('role') == 'admin':
                    remove_btn = QPushButton("Remove")
                    remove_btn.setProperty('param_index', i)
                    remove_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #dc2626;
                            color: white;
                            border: none;
                            border-radius: 6px;
                            padding: 8px 16px;
                            font-weight: 600;
                            font-size: 12px;
                        }
                        QPushButton:hover { background-color: #b91c1c; }
                    """)
                    remove_btn.clicked.connect(lambda checked, idx=i: self.remove_parameter(idx))
                    actions_layout.addWidget(remove_btn)
            
            table.setCellWidget(i, 5, actions_widget)
            table.setRowHeight(i, 70)
        
        self.table = table
        layout.addWidget(table)
    
    def toggle_parameter(self, index):
        if not self.auth_service:
            return
        param = self.parameters[index]
        new_enabled = not param['enabled']

        # Publish via MQTT so backend writes to PostgreSQL and emits
        # parameter_updated to frontend via Socket.IO
        if self.sync_service and hasattr(self.sync_service, 'mqtt'):
            import json
            mqtt = self.sync_service.mqtt
            if mqtt.is_connected:
                mqtt.client.publish(
                    'precisionpulse/sync/parameters',
                    json.dumps({
                        'type': 'parameter_updated',
                        'action': 'update',
                        'parameter': {**param, 'enabled': new_enabled},
                        'source': 'desktop',
                    }),
                    qos=1
                )

        # Optimistic local update
        self.parameters[index]['enabled'] = new_enabled
        if self.db:
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                conn.execute('UPDATE parameters SET enabled=? WHERE id=?', (1 if new_enabled else 0, param['id']))
                conn.commit()
        self.parameters_changed.emit()
        self._sort_parameters()
        self._rebuild_table()
    
    def _info_text(self) -> str:
        enabled = sum(1 for p in self.parameters if p['enabled'])
        total = len(self.parameters)
        return f"{enabled} of {total} parameters enabled. Desktop will collect and send only enabled parameters every 3 seconds."

    def _update_info_label(self):
        if self._info_label:
            self._info_label.setText(self._info_text())

    def _sort_parameters(self):
        self.parameters.sort(key=lambda p: (not p['enabled'], p.get('name', '')))
    
    def _on_parameters_fetched(self, parameters):
        """Sync parameter list and update table in-place (zero full rebuild)."""
        self.parameters = parameters
        self._sort_parameters()
        # If row count changed, we must rebuild; otherwise update cells in-place
        if not hasattr(self, 'table') or self.table is None or self.table.rowCount() != len(self.parameters):
            self._rebuild_table()
        else:
            self._update_table_cells()

    def _on_parameter_updated(self, parameter):
        """Handle single parameter update — update in-place, rebuild only if row count changes."""
        old_count = len(self.parameters)
        for i, p in enumerate(self.parameters):
            if p.get('id') == parameter.get('id'):
                self.parameters[i] = parameter
                break
        else:
            self.parameters.append(parameter)
        self._sort_parameters()
        if not self.isVisible():
            return
        if len(self.parameters) != old_count:
            self._rebuild_table()
        else:
            self._update_table_cells()

    def _update_table_cells(self):
        """Update every visible cell in-place — no widget destruction, zero flicker."""
        self._update_info_label()
        if not hasattr(self, 'table') or self.table is None:
            return
        for i, param in enumerate(self.parameters):
            if i >= self.table.rowCount():
                break
            # Status button
            sw = self.table.cellWidget(i, 0)
            if sw:
                btn = sw.findChild(QPushButton)
                if btn:
                    enabled = param['enabled']
                    tick = '\u2713' if enabled else '\u2717'
                    label = 'Enabled' if enabled else 'Disabled'
                    bg = '#059669' if enabled else '#dc2626'
                    hover = '#047857' if enabled else '#b91c1c'
                    btn.setText(f"{tick} {label}")
                    btn.setStyleSheet(
                        f"QPushButton {{ color: white; background-color: {bg};"
                        " padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 12px; border: none; text-align: left; }}"
                        f"QPushButton:hover {{ background-color: {hover}; }}"
                    )
            # Parameter name
            item = self.table.item(i, 1)
            if item:
                item.setText(param['name'])
            # Unit
            item = self.table.item(i, 2)
            if item:
                item.setText(param['unit'])
            # Alert range
            alert_min = param.get('alert_min')
            alert_max = param.get('alert_max')
            if alert_min is not None and alert_max is not None:
                range_text = f"{alert_min} \u2013 {alert_max}"
            elif alert_min is not None:
                range_text = f"\u2265 {alert_min}"
            elif alert_max is not None:
                range_text = f"\u2264 {alert_max}"
            else:
                range_text = "Not set"
            item = self.table.item(i, 3)
            if item:
                item.setText(range_text)
                from PySide6.QtGui import QColor
                item.setForeground(QColor('cyan') if (alert_min is not None or alert_max is not None) else QColor('gray'))
            # Description
            item = self.table.item(i, 4)
            if item:
                item.setText(param.get('description', ''))
    
    def _rebuild_table(self):
        """Remove old table and build a fresh one using the stored layout reference."""
        self._update_info_label()
        if self._table_container_layout and hasattr(self, 'table') and self.table:
            self._table_container_layout.removeWidget(self.table)
            self.table.deleteLater()
            self.table = None
        if self._table_container_layout:
            self.create_table(self._table_container_layout)

    def remove_parameter(self, index):
        if not self.auth_service:
            return
        user = self.auth_service.get_current_user()
        if not user or user.get('role') != 'admin':
            return
        param = self.parameters[index]
        msg = CustomMessageBox1("Confirm Action", "Do you want to delete this parameter?")
        if msg.exec() == QDialog.Accepted:
            if self.sync_service and hasattr(self.sync_service, 'mqtt'):
                import json as _json
                _mqtt = self.sync_service.mqtt
                if _mqtt.is_connected:
                    _mqtt.client.publish(
                        'precisionpulse/sync/parameters',
                        _json.dumps({'type': 'parameter_deleted', 'action': 'delete',
                                     'parameter': {'id': param['id']}, 'source': 'desktop'}),
                        qos=1
                    )
            if self.db:
                import sqlite3
                with sqlite3.connect(self.db.db_path) as conn:
                    conn.execute('DELETE FROM parameters WHERE id=?', (param['id'],))
                    conn.commit()
            self.parameters_changed.emit()
            self.parameters = self.get_default_parameters()
            self._rebuild_table()
    
    def set_alert_range(self, index):
        param = self.parameters[index]
        dialog = AlertRangeDialog(self, param)
        if dialog.exec():
            alert_min, alert_max = dialog.get_range()
            if self.sync_service and hasattr(self.sync_service, 'mqtt'):
                import json as _json
                _mqtt = self.sync_service.mqtt
                if _mqtt.is_connected:
                    _mqtt.client.publish(
                        'precisionpulse/sync/parameters',
                        _json.dumps({'type': 'parameter_updated', 'action': 'update',
                                     'parameter': {**param, 'alert_min': alert_min, 'alert_max': alert_max},
                                     'source': 'desktop'}),
                        qos=1
                    )
            self.parameters[index]['alert_min'] = alert_min
            self.parameters[index]['alert_max'] = alert_max
            # Write to local SQLite so TelemetryService._build_parameters_dict picks up thresholds
            if self.db:
                import sqlite3
                try:
                    with sqlite3.connect(self.db.db_path) as conn:
                        conn.execute(
                            'UPDATE parameters SET alert_min=?, alert_max=? WHERE id=?',
                            (alert_min, alert_max, param['id'])
                        )
                        conn.commit()
                except Exception as e:
                    print(f"[PARAMS] SQLite alert range update error: {e}")
            # Notify telemetry service to refresh parameter thresholds
            self.parameters_changed.emit()
            self._rebuild_table()

    def add_parameter(self):
        if not self.auth_service:
            return
        user = self.auth_service.get_current_user()
        if not user or user.get('role') != 'admin':
            return
        from PySide6.QtWidgets import QApplication
        overlay = QWidget(self)
        overlay.setGeometry(self.rect())
        overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.5);")
        overlay.show()
        dialog = AddParameterDialog(self, self.parameters)
        screen = QApplication.primaryScreen().geometry()
        dialog.move(screen.center().x() - dialog.width() // 2, screen.center().y() - dialog.height() // 2)
        result = dialog.exec()
        overlay.deleteLater()
        if result:
            param_data = dialog.get_parameter_data()
            if self.sync_service and hasattr(self.sync_service, 'mqtt'):
                import json as _json
                _mqtt = self.sync_service.mqtt
                if _mqtt.is_connected:
                    _mqtt.client.publish(
                        'precisionpulse/sync/parameters',
                        _json.dumps({'type': 'parameter_created', 'action': 'create',
                                     'parameter': {'name': param_data['name'], 'unit': param_data['unit'],
                                                   'description': param_data['description'],
                                                   'enabled': param_data['enabled']},
                                     'source': 'desktop'}),
                        qos=1
                    )
            self.parameters_changed.emit()
            self.parameters = self.get_default_parameters()
            self._rebuild_table()

    def get_default_parameters(self):
        """Load parameters from local SQLite (synced from backend via MQTT)."""
        if self.db:
            import sqlite3
            try:
                with sqlite3.connect(self.db.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        'SELECT id, name, unit, description, enabled, alert_min, alert_max, warn_min, warn_max FROM parameters ORDER BY name'
                    )
                    params = [
                        {'id': r[0], 'name': r[1], 'unit': r[2],
                         'description': r[3] or '', 'enabled': bool(r[4]),
                         'alert_min': r[5], 'alert_max': r[6],
                         'warn_min': r[7], 'warn_max': r[8]}
                        for r in cursor.fetchall()
                    ]
                    if params:
                        self._sort_parameters_list(params)
                        return params
            except Exception as e:
                print(f'[PARAMS] SQLite read error: {e}')
        return []
    
    def _sort_parameters_list(self, params):
        """Sort a parameters list: enabled first, then disabled"""
        params.sort(key=lambda p: (not p['enabled'], p.get('name', '')))


class AddParameterDialog(QDialog):
    """Dialog for adding new parameters"""
    
    def __init__(self, parent=None, existing_parameters=None):
        super().__init__(parent)
        self.existing_parameters = existing_parameters or []
        self.setup_ui()
    
    def setup_ui(self):
        """Setup dialog UI"""
        self.setWindowTitle("")
        self.setModal(True)
        self.setFixedSize(500, 580)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Main container with rounded corners
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #374151;
                border-radius: 16px;
            }
        """)
        
        layout = QVBoxLayout(container)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title_label = QLabel("Add New Parameter")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 700;
                color: white;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title_label)
        
        # Parameter Name
        name_label = QLabel("Parameter Name")
        name_label.setStyleSheet("color: #e5e7eb; font-size: 14px; font-weight: 600;")
        layout.addWidget(name_label)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Temperature")
        self.name_input.setFixedHeight(45)
        self.name_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 0 16px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        layout.addWidget(self.name_input)
        
        # Unit
        unit_label = QLabel("Unit")
        unit_label.setStyleSheet("color: #e5e7eb; font-size: 14px; font-weight: 600; margin-top: 10px;")
        layout.addWidget(unit_label)
        
        self.unit_input = QLineEdit()
        self.unit_input.setPlaceholderText("e.g., °C, kPa, L/s")
        self.unit_input.setFixedHeight(45)
        self.unit_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 0 16px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        layout.addWidget(self.unit_input)
        
        # Description
        desc_label = QLabel("Description")
        desc_label.setStyleSheet("color: #e5e7eb; font-size: 14px; font-weight: 600; margin-top: 10px;")
        layout.addWidget(desc_label)
        
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Brief description of this parameter")
        self.desc_input.setFixedHeight(100)
        self.desc_input.setStyleSheet("""
            QTextEdit {
                background-color: #1e293b;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 12px;
                color: white;
                font-size: 14px;
            }
            QTextEdit:focus {
                border-color: #3b82f6;
            }
        """)
        layout.addWidget(self.desc_input)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        add_btn = QPushButton("Add Parameter")
        add_btn.setFixedHeight(45)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 24px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        add_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(45)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #4b5563;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 24px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #374151;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(add_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        main_layout.addWidget(container)
    
    def get_parameter_data(self):
        """Get parameter data from form"""
        import time
        return {
            'id': f"param_{int(time.time())}",
            'name': self.name_input.text() or "New Parameter",
            'unit': self.unit_input.text() or "unit",
            'description': self.desc_input.toPlainText() or "No description",
            'enabled': True
        }
    
    def accept(self):
        """Validate and accept dialog"""
        name = self.name_input.text().strip()
        unit = self.unit_input.text().strip()
        
        if not name:
            from src.ui.CustomMessageBox import CustomMessageBox
            msg = CustomMessageBox("Validation Error", "Parameter name is required")
            msg.exec()
            return
        
        if not unit:
            from src.ui.CustomMessageBox import CustomMessageBox
            msg = CustomMessageBox("Validation Error", "Parameter unit is required")
            msg.exec()
            return
        
        # Check for duplicate parameter name
        for param in self.existing_parameters:
            if param['name'].lower() == name.lower():
                from src.ui.CustomMessageBox import CustomMessageBox
                msg = CustomMessageBox("Validation Error", f"Parameter '{name}' already exists")
                msg.exec()
                return        
        super().accept()


class AlertRangeDialog(QDialog):
    """Dialog for configuring alert min/max range for a parameter."""

    def __init__(self, parent=None, param=None):
        super().__init__(parent)
        self.param = param or {}
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("")
        self.setModal(True)
        self.setFixedSize(420, 340)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setStyleSheet("QFrame { background-color: #374151; border-radius: 16px; }")
        layout = QVBoxLayout(container)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 28, 28, 28)

        title = QLabel(f"Set Alert Range — {self.param.get('name', 'Parameter')}")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: white;")
        layout.addWidget(title)

        subtitle = QLabel("Values outside this range will be highlighted in red and logged as alerts.")
        subtitle.setStyleSheet("font-size: 12px; color: #94a3b8;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        min_label = QLabel("Minimum Value (alert if below)")
        min_label.setStyleSheet("color: #e5e7eb; font-size: 13px; font-weight: 600; margin-top: 8px;")
        layout.addWidget(min_label)

        self.min_input = QLineEdit()
        self.min_input.setPlaceholderText("e.g., 20  (leave blank to disable)")
        self.min_input.setFixedHeight(42)
        current_min = self.param.get('alert_min')
        if current_min is not None:
            self.min_input.setText(str(current_min))
        self.min_input.setStyleSheet("""
            QLineEdit { background-color: #1e293b; border: 1px solid #4b5563;
                border-radius: 8px; padding: 0 14px; color: white; font-size: 14px; }
            QLineEdit:focus { border-color: #7c3aed; }
        """)
        layout.addWidget(self.min_input)

        max_label = QLabel("Maximum Value (alert if above)")
        max_label.setStyleSheet("color: #e5e7eb; font-size: 13px; font-weight: 600;")
        layout.addWidget(max_label)

        self.max_input = QLineEdit()
        self.max_input.setPlaceholderText("e.g., 60  (leave blank to disable)")
        self.max_input.setFixedHeight(42)
        current_max = self.param.get('alert_max')
        if current_max is not None:
            self.max_input.setText(str(current_max))
        self.max_input.setStyleSheet("""
            QLineEdit { background-color: #1e293b; border: 1px solid #4b5563;
                border-radius: 8px; padding: 0 14px; color: white; font-size: 14px; }
            QLineEdit:focus { border-color: #7c3aed; }
        """)
        layout.addWidget(self.max_input)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        save_btn = QPushButton("Save")
        save_btn.setFixedHeight(42)
        save_btn.setStyleSheet("""
            QPushButton { background-color: #7c3aed; color: white; border: none;
                border-radius: 8px; font-weight: 600; font-size: 14px; }
            QPushButton:hover { background-color: #6d28d9; }
        """)
        save_btn.clicked.connect(self._validate_and_accept)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(42)
        cancel_btn.setStyleSheet("""
            QPushButton { background-color: #4b5563; color: white; border: none;
                border-radius: 8px; font-weight: 600; font-size: 14px; }
            QPushButton:hover { background-color: #374151; }
        """)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        main_layout.addWidget(container)

    def _validate_and_accept(self):
        min_text = self.min_input.text().strip()
        max_text = self.max_input.text().strip()
        try:
            if min_text:
                float(min_text)
            if max_text:
                float(max_text)
            if min_text and max_text and float(min_text) >= float(max_text):
                from src.ui.CustomMessageBox import CustomMessageBox
                CustomMessageBox("Validation Error", "Minimum must be less than maximum.").exec()
                return
        except ValueError:
            from src.ui.CustomMessageBox import CustomMessageBox
            CustomMessageBox("Validation Error", "Please enter valid numeric values.").exec()
            return
        self.accept()

    def get_range(self):
        """Return (alert_min, alert_max) — None if blank."""
        min_text = self.min_input.text().strip()
        max_text = self.max_input.text().strip()
        return (
            float(min_text) if min_text else None,
            float(max_text) if max_text else None,
        )
