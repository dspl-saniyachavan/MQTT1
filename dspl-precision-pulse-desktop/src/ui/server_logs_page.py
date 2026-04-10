"""
Server logs page for displaying all changes and records
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QLabel, QSpinBox, QHeaderView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from src.services.server_log_service import ServerLogService


class ServerLogsPage(QWidget):
    """Page for viewing server logs"""
    
    def __init__(self, server_log_service: ServerLogService):
        super().__init__()
        self.server_log_service = server_log_service
        self.init_ui()
        self.load_logs()
        
        # Auto-refresh logs every 5 seconds
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_logs)
        self.refresh_timer.start(5000)
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Server Logs"))
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Filters
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Event Type:"))
        self.event_type_combo = QComboBox()
        self.event_type_combo.addItems([
            "All",
            "TELEMETRY",
            "SYNC",
            "MQTT",
            "AUTH",
            "CONFIG",
            "PARAMETER",
            "USER_MANAGEMENT",
            "PERMISSION"
        ])
        self.event_type_combo.currentTextChanged.connect(self.load_logs)
        filter_layout.addWidget(self.event_type_combo)
        
        filter_layout.addWidget(QLabel("Limit:"))
        self.limit_spinbox = QSpinBox()
        self.limit_spinbox.setMinimum(10)
        self.limit_spinbox.setMaximum(1000)
        self.limit_spinbox.setValue(100)
        self.limit_spinbox.valueChanged.connect(self.load_logs)
        filter_layout.addWidget(self.limit_spinbox)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_logs)
        filter_layout.addWidget(refresh_btn)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Logs table
        self.logs_table = QTableWidget()
        self.logs_table.setColumnCount(11)
        self.logs_table.setHorizontalHeaderLabels([
            "ID", "Event Type", "Resource Type", "Resource ID", "Action",
            "Old Value", "New Value", "Status", "Error", "Timestamp", "User"
        ])
        self.logs_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.logs_table)
        
        self.setLayout(layout)
    
    def load_logs(self):
        """Load logs from database"""
        try:
            event_type = self.event_type_combo.currentText()
            limit = self.limit_spinbox.value()
            
            if event_type == "All":
                logs = self.server_log_service.get_logs(limit=limit)
            else:
                logs = self.server_log_service.get_logs_by_event_type(event_type, limit=limit)
            
            self.display_logs(logs)
        except Exception as e:
            print(f"Error loading logs: {e}")
    
    def display_logs(self, logs):
        """Display logs in table"""
        self.logs_table.setRowCount(len(logs))
        
        for row, log in enumerate(logs):
            # ID
            self.logs_table.setItem(row, 0, QTableWidgetItem(str(log['id'])))
            
            # Event Type
            event_item = QTableWidgetItem(log['event_type'])
            self.logs_table.setItem(row, 1, event_item)
            
            # Resource Type
            self.logs_table.setItem(row, 2, QTableWidgetItem(log['resource_type']))
            
            # Resource ID
            self.logs_table.setItem(row, 3, QTableWidgetItem(log['resource_id'] or ''))
            
            # Action
            self.logs_table.setItem(row, 4, QTableWidgetItem(log['action']))
            
            # Old Value
            self.logs_table.setItem(row, 5, QTableWidgetItem(log['old_value'] or ''))
            
            # New Value
            self.logs_table.setItem(row, 6, QTableWidgetItem(log['new_value'] or ''))
            
            # Status
            status_item = QTableWidgetItem(log['status'])
            if log['status'] == 'failed':
                status_item.setBackground(QColor(255, 200, 200))
            elif log['status'] == 'success':
                status_item.setBackground(QColor(200, 255, 200))
            self.logs_table.setItem(row, 7, status_item)
            
            # Error Message
            self.logs_table.setItem(row, 8, QTableWidgetItem(log['error_message'] or ''))
            
            # Timestamp
            self.logs_table.setItem(row, 9, QTableWidgetItem(log['timestamp']))
            
            # User Email
            self.logs_table.setItem(row, 10, QTableWidgetItem(log['user_email'] or ''))
    
    def closeEvent(self, event):
        """Stop refresh timer on close"""
        self.refresh_timer.stop()
        super().closeEvent(event)
