"""
Edit Parameter Values Page for Desktop Application
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QFrame, QGridLayout, QDoubleSpinBox, QMessageBox,
                               QScrollArea, QDialog, QLineEdit)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QDateTime
from PySide6.QtGui import QFont, QColor
from src.core.database import DatabaseManager
from src.core.auth_service import AuthService
from src.services.parameter_sync_service import ParameterSyncService
import json
from datetime import datetime

_STYLE_DARK_TEXT = "color: #111827; background: transparent;"
_STYLE_MUTED_TEXT = "color: #94a3b8; font-size: 16px;"
_LABEL_EDIT_VALUE = "Edit Value"

class EditValuesPage(QWidget):
    """Page for editing parameter values"""
    
    back_clicked = Signal()
    values_updated = Signal(dict)
    
    def __init__(self, db: DatabaseManager, auth_service: AuthService,
                 parameter_sync_service: ParameterSyncService, telemetry_service=None):
        super().__init__()
        self.db = db
        self.auth_service = auth_service
        self.parameter_sync_service = parameter_sync_service
        self.telemetry_service = telemetry_service
        
        # Store parameter widgets for easy access
        self.parameter_widgets = {}
        self.parameter_values = {}
        self.editing_states = {}
        self._increment_timers: dict = {}   # param_id -> QTimer for auto-increment
        
        # Setup UI
        self.setup_ui()
        
        self._editing_params: set = set()  # param_ids currently being edited
        
        # Setup refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_values)
        self.refresh_timer.start(3000)  # Refresh every 3 seconds
        
        # Load initial data
        self.load_parameters()
    
    def setup_ui(self):
        """Setup the UI matching frontend design"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header - matching frontend gray header
        header_frame = QFrame()
        header_frame.setFixedHeight(80)
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #d1d5db;
                border: none;
                border-bottom: 1px solid #9ca3af;
            }
        """)
        
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(30, 0, 30, 0)
        
        # Logo and title section
        logo_title_layout = QHBoxLayout()
        
        logo_label = QLabel("📊")
        logo_label.setStyleSheet("font-size: 24px; background: transparent;")
        logo_title_layout.addWidget(logo_label)
        
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        title_label = QLabel("PrecisionPulse")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(_STYLE_DARK_TEXT)
        title_layout.addWidget(title_label)
        
        subtitle_label = QLabel("Edit Values")
        subtitle_font = QFont()
        subtitle_font.setPointSize(10)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("color: #4b5563; background: transparent;")
        title_layout.addWidget(subtitle_label)
        
        logo_title_layout.addLayout(title_layout)
        header_layout.addLayout(logo_title_layout)
        header_layout.addStretch()
        
        # Back button
        back_btn = QPushButton("Back")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #111827;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
            }
        """)
        back_btn.clicked.connect(self.back_clicked.emit)
        header_layout.addWidget(back_btn)
        
        layout.addWidget(header_frame)
        
        # Main content area
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        # Title section
        title_section = QVBoxLayout()
        title_section.setSpacing(5)
        
        page_title = QLabel("Edit Parameter Values")
        page_title_font = QFont()
        page_title_font.setPointSize(24)
        page_title_font.setBold(True)
        page_title.setFont(page_title_font)
        page_title.setStyleSheet("color: white; background: transparent;")
        title_section.addWidget(page_title)
        
        page_subtitle = QLabel("Update parameter values in real-time")
        page_subtitle_font = QFont()
        page_subtitle_font.setPointSize(11)
        page_subtitle.setFont(page_subtitle_font)
        page_subtitle.setStyleSheet("color: #9ca3af; background: transparent;")
        title_section.addWidget(page_subtitle)
        
        main_layout.addLayout(title_section)
        
        # Messages area
        self.messages_layout = QVBoxLayout()
        self.messages_layout.setSpacing(10)
        main_layout.addLayout(self.messages_layout)
        
        # Info box
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(59, 130, 246, 0.1);
                border-left: 4px solid #3b82f6;
                border-radius: 4px;
                padding: 15px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        info_label = QLabel("Update parameter values below. Changes will be synchronized across all connected devices.")
        info_label.setStyleSheet("color: #1e40af; background: transparent; font-size: 13px;")
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        main_layout.addWidget(info_frame)
        
        # Scroll area for parameters
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: #0f172a;
                border: none;
            }
            QScrollBar:vertical {
                background: #1a1f3a;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #4f46e5;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6366f1;
            }
        """)
        
        # Content widget for parameters
        content_widget = QWidget()
        self.parameters_layout = QVBoxLayout(content_widget)
        self.parameters_layout.setSpacing(15)
        self.parameters_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Wrap main layout in a frame
        main_frame = QFrame()
        main_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f172a, stop:0.5 #1a1f3a, stop:1 #0f172a);
                border: none;
            }
        """)
        main_frame.setLayout(main_layout)
        layout.addWidget(main_frame)
    
    def load_parameters(self):
        """Load parameters from database"""
        try:
            # Get enabled parameters
            enabled_params = self.db.get_enabled_parameters()
            
            # Clear existing widgets
            self.parameter_widgets.clear()
            self.editing_states.clear()
            
            # Clear layout
            while self.parameters_layout.count():
                item = self.parameters_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            if not enabled_params:
                no_params_label = QLabel("No enabled parameters")
                no_params_label.setStyleSheet(_STYLE_MUTED_TEXT)
                no_params_label.setAlignment(Qt.AlignCenter)
                self.parameters_layout.addWidget(no_params_label)
                return
            
            # Create parameter cards in grid (3 columns)
            grid_layout = QGridLayout()
            grid_layout.setSpacing(15)
            
            row = 0
            col = 0
            for param in enabled_params:
                param_card = self.create_parameter_card(param)
                grid_layout.addWidget(param_card, row, col)
                
                col += 1
                if col >= 3:
                    col = 0
                    row += 1
            
            self.parameters_layout.addLayout(grid_layout)
            self.parameters_layout.addStretch()
            
            # Refresh values
            self.refresh_values()
            
        except Exception as e:
            print(f"Error loading parameters: {e}")
            self.show_error(f"Failed to load parameters: {str(e)}")
    
    def create_parameter_card(self, param: dict) -> QFrame:
        """Create a parameter card widget matching frontend design"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: none;
            }
        """)
        card.setMinimumHeight(300)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Parameter name
        name_label = QLabel(param.get('name', 'Unknown'))
        name_font = QFont()
        name_font.setPointSize(13)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet(_STYLE_DARK_TEXT)
        layout.addWidget(name_label)
        
        # Description
        if param.get('description'):
            desc_label = QLabel(param.get('description'))
            desc_label.setStyleSheet("color: #6b7280; background: transparent; font-size: 12px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        # Current value display box
        value_frame = QFrame()
        value_frame.setStyleSheet("""
            QFrame {
                background-color: #f3f4f6;
                border: none;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        value_layout = QVBoxLayout(value_frame)
        value_layout.setSpacing(5)
        
        current_label = QLabel("Current Value")
        current_label.setStyleSheet("color: #6b7280; background: transparent; font-size: 12px;")
        value_layout.addWidget(current_label)
        
        current_value_label = QLabel("Loading...")
        current_value_font = QFont()
        current_value_font.setPointSize(18)
        current_value_font.setBold(True)
        current_value_label.setFont(current_value_font)
        current_value_label.setStyleSheet(_STYLE_DARK_TEXT)
        value_layout.addWidget(current_value_label)
        
        timestamp_label = QLabel("")
        timestamp_label.setStyleSheet("color: #9ca3af; background: transparent; font-size: 11px;")
        value_layout.addWidget(timestamp_label)
        
        layout.addWidget(value_frame)
        
        # Store references
        param_id = param.get('id')
        self.parameter_widgets[param_id] = {
            'current_label': current_value_label,
            'timestamp_label': timestamp_label,
            'unit': param.get('unit', ''),
            'card': card
        }
        self.editing_states[param_id] = False
        
        # Input and button container
        input_container = QVBoxLayout()
        input_container.setSpacing(10)
        
        # Input field
        input_field = QDoubleSpinBox()
        input_field.setRange(-999999, 999999)
        input_field.setDecimals(2)
        input_field.setStyleSheet("""
            QDoubleSpinBox {
                background-color: white;
                color: #111827;
                border: 2px solid #e5e7eb;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }
            QDoubleSpinBox:focus {
                border: 2px solid #3b82f6;
            }
        """)
        input_field.setVisible(False)
        input_container.addWidget(input_field)
        
        # Button container
        button_container = QHBoxLayout()
        button_container.setSpacing(10)
        
        # Edit/Save button
        edit_btn = QPushButton(_LABEL_EDIT_VALUE)
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
        """)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #d1d5db;
                color: #111827;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #9ca3af;
            }
        """)
        cancel_btn.setVisible(False)
        
        def toggle_edit():
            is_editing = self.editing_states[param_id]
            if not is_editing:
                # Enter edit mode — freeze refresh for this param
                self._editing_params.add(param_id)
                current_value = self.parameter_values.get(param_id, 0)
                input_field.setValue(current_value)
                input_field.setVisible(True)
                cancel_btn.setVisible(True)
                edit_btn.setText("Save Value")
                edit_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #10b981;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 10px 15px;
                        font-weight: 600;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: #059669;
                    }
                """)
                self.editing_states[param_id] = True
            else:
                # Save value
                self.save_parameter_value(param_id, input_field.value(), param.get('name'))
        
        def cancel_edit():
            self._editing_params.discard(param_id)
            self._stop_increment(param_id)
            input_field.setVisible(False)
            cancel_btn.setVisible(False)
            edit_btn.setText(_LABEL_EDIT_VALUE)
            edit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 15px;
                    font-weight: 600;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #2563eb;
                }
            """)
            self.editing_states[param_id] = False
        
        edit_btn.clicked.connect(toggle_edit)
        cancel_btn.clicked.connect(cancel_edit)
        
        button_container.addWidget(edit_btn)
        button_container.addWidget(cancel_btn)
        input_container.addLayout(button_container)
        
        layout.addLayout(input_container)
        layout.addStretch()
        
        # Store input field reference
        self.parameter_widgets[param_id]['input_field'] = input_field
        self.parameter_widgets[param_id]['edit_btn'] = edit_btn
        self.parameter_widgets[param_id]['cancel_btn'] = cancel_btn
        
        return card
    
    def refresh_values(self):
        """Refresh parameter values from local SQLite — skip params currently being edited."""
        try:
            import sqlite3
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ps.parameter_id, ps.value, ps.timestamp
                    FROM parameter_stream ps
                    INNER JOIN (
                        SELECT parameter_id, MAX(timestamp) AS max_ts
                        FROM parameter_stream GROUP BY parameter_id
                    ) latest ON ps.parameter_id = latest.parameter_id
                        AND ps.timestamp = latest.max_ts
                """)
                for param_id, value, timestamp in cursor.fetchall():
                    # Skip parameters currently open in the edit form
                    if param_id in self._editing_params:
                        continue
                    if param_id in self.parameter_widgets:
                        widget_info = self.parameter_widgets[param_id]
                        unit = widget_info['unit']
                        widget_info['current_label'].setText(f"{value:.2f} {unit}")
                        try:
                            dt = datetime.fromisoformat(timestamp)
                            widget_info['timestamp_label'].setText(dt.strftime('%I:%M %p'))
                        except Exception:
                            pass
                        self.parameter_values[param_id] = value
        except Exception as e:
            print(f"[EDIT_VALUES] Error refreshing values: {e}")
    
    def save_parameter_value(self, param_id: int, value: float, param_name: str):
        """Save parameter value via MQTT, then hand off auto-increment to telemetry_service."""
        try:
            from datetime import datetime
            local_ts = datetime.now().isoformat()

            try:
                self.db.store_parameter_stream(param_id, value, timestamp=local_ts)
            except Exception as db_err:
                print(f"[EDIT_VALUES] SQLite write error: {db_err}")

            if self.telemetry_service and self.telemetry_service.mqtt_service.is_connected:
                import json as _json
                payload = {'parameter_id': param_id, 'value': value,
                           'timestamp': local_ts, 'source': 'admin'}
                self.telemetry_service.mqtt_service.client.publish(
                    f'precisionpulse/{self.telemetry_service.mqtt_service.device_id}/parameter/edit',
                    _json.dumps(payload), qos=1
                )
                print(f"[EDIT_VALUES] Published admin edit param {param_id}={value} via MQTT")
            else:
                print("[EDIT_VALUES] MQTT offline — value saved locally only")

            unit = self.parameter_widgets[param_id]['unit']
            self.parameter_widgets[param_id]['current_label'].setText(f"{value:.2f} {unit}")
            self.editing_states[param_id] = False
            self.parameter_widgets[param_id]['input_field'].setVisible(False)
            self.parameter_widgets[param_id]['cancel_btn'].setVisible(False)
            edit_btn = self.parameter_widgets[param_id]['edit_btn']
            edit_btn.setText(_LABEL_EDIT_VALUE)
            edit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6; color: white; border: none;
                    border-radius: 6px; padding: 10px 15px;
                    font-weight: 600; font-size: 13px;
                }
                QPushButton:hover { background-color: #2563eb; }
            """)
            self.show_success(f"Parameter '{param_name}' updated to {value:.2f}")
            self.values_updated.emit({'parameter_id': param_id, 'value': value})
            self.parameter_values[param_id] = value

            if self.telemetry_service:
                self.telemetry_service._on_admin_parameter_value_updated(
                    {'parameter_id': param_id, 'value': value, 'timestamp': local_ts}
                )

            self._stop_increment(param_id)
            self._editing_params.discard(param_id)
            # Do NOT start any auto-increment timer — the telemetry service
            # will naturally drift from the saved value on its own schedule.
            # Starting a timer here caused the UI to show continuously
            # incrementing values after every admin save.

        except Exception as e:
            print(f"[EDIT_VALUES] Error: {e}")


    def _stop_increment(self, param_id: int):
        """Stop the auto-increment timer for a parameter."""
        timer = self._increment_timers.pop(param_id, None)
        if timer:
            timer.stop()
    
    def show_success(self, message: str):
        """Show success message"""
        # Clear previous messages
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        msg_frame = QFrame()
        msg_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(16, 185, 129, 0.1);
                border-left: 4px solid #10b981;
                border-radius: 4px;
                padding: 12px;
            }
        """)
        msg_layout = QVBoxLayout(msg_frame)
        msg_label = QLabel(message)
        msg_label.setStyleSheet("color: #047857; background: transparent; font-weight: 600; font-size: 13px;")
        msg_layout.addWidget(msg_label)
        self.messages_layout.addWidget(msg_frame)
        
        # Auto-hide after 3 seconds
        QTimer.singleShot(3000, lambda: self.clear_messages())
    
    def show_error(self, message: str):
        """Show error message"""
        # Clear previous messages
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        msg_frame = QFrame()
        msg_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(239, 68, 68, 0.1);
                border-left: 4px solid #ef4444;
                border-radius: 4px;
                padding: 12px;
            }
        """)
        msg_layout = QVBoxLayout(msg_frame)
        msg_label = QLabel(message)
        msg_label.setStyleSheet("color: #991b1b; background: transparent; font-weight: 600; font-size: 13px;")
        msg_layout.addWidget(msg_label)
        self.messages_layout.addWidget(msg_frame)
        
        # Auto-hide after 5 seconds
        QTimer.singleShot(5000, lambda: self.clear_messages())
    
    def clear_messages(self):
        """Clear all messages"""
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def closeEvent(self, event):
        """Handle page close"""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        for timer in self._increment_timers.values():
            timer.stop()
        self._increment_timers.clear()
        event.accept()
