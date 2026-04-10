"""
Configuration Management Page for Desktop Application
Displays and monitors system configuration settings
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
                               QMessageBox, QLineEdit, QComboBox, QDialog, QSpinBox)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QDateTime
from PySide6.QtGui import QFont, QColor
from src.services.configuration_service import ConfigurationService
from src.core.auth_service import AuthService
from src.core.database import DatabaseManager
from datetime import datetime

class ConfigurationPage(QWidget):
    """Page for viewing and monitoring system configuration"""
    
    back_clicked = Signal()
    config_changed = Signal(dict)
    
    def __init__(self, db: DatabaseManager, auth_service: AuthService, 
                 config_service: ConfigurationService):
        super().__init__()
        self.db = db
        self.auth_service = auth_service
        self.config_service = config_service
        
        # Setup UI
        self.setup_ui()
        
        # Setup refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_configs)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
        
        # Connect live config_changed signal for instant UI refresh
        try:
            self.config_service.config_changed.connect(self._on_live_config_change)
        except Exception:
            pass
        
        # Load initial data
        self.load_configurations()
    
    def setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
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
        
        # Logo and title
        logo_label = QLabel("⚙️")
        logo_label.setStyleSheet("font-size: 24px; background: transparent;")
        header_layout.addWidget(logo_label)
        
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        title_label = QLabel("PrecisionPulse")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #111827; background: transparent;")
        title_layout.addWidget(title_label)
        
        subtitle_label = QLabel("System Configuration")
        subtitle_font = QFont()
        subtitle_font.setPointSize(10)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("color: #4b5563; background: transparent;")
        title_layout.addWidget(subtitle_label)
        
        header_layout.addLayout(title_layout)
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
        
        # Main content
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        # Title section
        title_section = QVBoxLayout()
        title_section.setSpacing(5)
        
        page_title = QLabel("System Configuration")
        page_title_font = QFont()
        page_title_font.setPointSize(24)
        page_title_font.setBold(True)
        page_title.setFont(page_title_font)
        page_title.setStyleSheet("color: white; background: transparent;")
        title_section.addWidget(page_title)
        
        page_subtitle = QLabel("View and monitor system configuration settings")
        page_subtitle_font = QFont()
        page_subtitle_font.setPointSize(11)
        page_subtitle.setFont(page_subtitle_font)
        page_subtitle.setStyleSheet("color: #9ca3af; background: transparent;")
        title_section.addWidget(page_subtitle)
        
        main_layout.addLayout(title_section)
        
        # Status bar
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(59, 130, 246, 0.1);
                border-left: 4px solid #3b82f6;
                border-radius: 4px;
                padding: 15px;
            }
        """)
        status_layout = QHBoxLayout(status_frame)
        
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #1e40af; background: transparent; font-size: 13px;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        main_layout.addWidget(status_frame)
        
        # Configuration table
        self.config_table = QTableWidget()
        self.config_table.setColumnCount(6)
        self.config_table.setHorizontalHeaderLabels([
            'Key', 'Value', 'Category', 'Data Type', 'Version', 'Updated'
        ])
        self.config_table.setStyleSheet("""
            QTableWidget {
                background-color: #0f172a;
                color: white;
                gridline-color: #1a1f3a;
                border: none;
            }
            QTableWidget::item {
                padding: 8px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #1e40af;
            }
            QHeaderView::section {
                background-color: #1a1f3a;
                color: #9ca3af;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        
        header = self.config_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
        main_layout.addWidget(self.config_table)
        
        # Pagination controls
        pagination_layout = QHBoxLayout()
        pagination_layout.addStretch()

        self.prev_btn = QPushButton("← Prev")
        self.prev_btn.setStyleSheet("""
            QPushButton { background-color: #334155; color: white; border: none;
                border-radius: 6px; padding: 6px 14px; font-weight: 600; }
            QPushButton:hover { background-color: #475569; }
            QPushButton:disabled { background-color: #1e293b; color: #475569; }
        """)
        self.prev_btn.clicked.connect(self._prev_page)

        self.page_label = QLabel("Page 1 / 1")
        self.page_label.setStyleSheet("color: #94a3b8; font-size: 12px; background: transparent;")
        self.page_label.setAlignment(Qt.AlignCenter)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setStyleSheet("""
            QPushButton { background-color: #334155; color: white; border: none;
                border-radius: 6px; padding: 6px 14px; font-weight: 600; }
            QPushButton:hover { background-color: #475569; }
            QPushButton:disabled { background-color: #1e293b; color: #475569; }
        """)
        self.next_btn.clicked.connect(self._next_page)

        pagination_layout.addWidget(self.prev_btn)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_btn)
        pagination_layout.addStretch()
        main_layout.addLayout(pagination_layout)

        self._config_page = 1
        self._config_page_size = 20
        self._all_configs: list = []
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_configs)
        button_layout.addWidget(refresh_btn)
        
        main_layout.addLayout(button_layout)
        
        # Wrap in frame
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
    
    def load_configurations(self):
        """Load configurations from service"""
        try:
            configs = self.config_service.get_all_configs()
            version = self.config_service.get_config_version()
            
            self.update_table(configs)
            self.update_status(len(configs), version)
            
        except Exception as e:
            print(f"Error loading configurations: {e}")
            self.show_error(f"Failed to load configurations: {str(e)}")
    
    def update_table(self, configs: dict):
        """Update configuration table with pagination"""
        HIDDEN_KEYS = {'AUTO_FLUSH_ENABLED', 'BUFFER_SIZE', 'HEARTBEAT_INTERVAL', 'SYNC_INTERVAL'}
        self._all_configs = [
            (key, config) for key, config in sorted(configs.items())
            if key.upper() not in HIDDEN_KEYS
        ]
        self._render_config_page()

    def _render_config_page(self):
        """Render the current page of configs into the table."""
        import math
        total = len(self._all_configs)
        total_pages = max(1, math.ceil(total / self._config_page_size))
        self._config_page = max(1, min(self._config_page, total_pages))

        start = (self._config_page - 1) * self._config_page_size
        page_items = self._all_configs[start: start + self._config_page_size]

        self.config_table.setRowCount(0)
        for key, config in page_items:
            row = self.config_table.rowCount()
            self.config_table.insertRow(row)

            key_item = QTableWidgetItem(key)
            key_item.setForeground(QColor("#ffffff"))
            key_item.setFont(QFont("Courier", 10))
            self.config_table.setItem(row, 0, key_item)

            value = config.get('value', '')
            if config.get('is_sensitive'):
                value = '***'
            value_item = QTableWidgetItem(value)
            value_item.setForeground(QColor("#10b981"))
            value_item.setFont(QFont("Courier", 10))
            self.config_table.setItem(row, 1, value_item)

            category_item = QTableWidgetItem(config.get('category', '-'))
            category_item.setForeground(QColor("#60a5fa"))
            self.config_table.setItem(row, 2, category_item)

            dtype_item = QTableWidgetItem(config.get('data_type', 'string'))
            dtype_item.setForeground(QColor("#a78bfa"))
            self.config_table.setItem(row, 3, dtype_item)

            version_item = QTableWidgetItem(f"v{config.get('version', 1)}")
            version_item.setForeground(QColor("#fbbf24"))
            self.config_table.setItem(row, 4, version_item)

            updated_at = config.get('updated_at', '')
            if updated_at:
                try:
                    dt = datetime.fromisoformat(updated_at)
                    updated_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    updated_str = updated_at
            else:
                updated_str = '-'
            updated_item = QTableWidgetItem(updated_str)
            updated_item.setForeground(QColor("#9ca3af"))
            self.config_table.setItem(row, 5, updated_item)

        self.page_label.setText(f"Page {self._config_page} / {total_pages}  ({total} configs)")
        self.prev_btn.setEnabled(self._config_page > 1)
        self.next_btn.setEnabled(self._config_page < total_pages)

    def _prev_page(self):
        if self._config_page > 1:
            self._config_page -= 1
            self._render_config_page()

    def _next_page(self):
        import math
        total_pages = max(1, math.ceil(len(self._all_configs) / self._config_page_size))
        if self._config_page < total_pages:
            self._config_page += 1
            self._render_config_page()
    
    def update_status(self, count: int, version: int):
        """Update status label"""
        last_sync = self.config_service.last_sync
        if last_sync:
            sync_time = last_sync.strftime('%H:%M:%S')
        else:
            sync_time = 'Never'
        
        status_text = f"Total: {count} | Version: {version} | Last Sync: {sync_time}"
        self.status_label.setText(status_text)
    
    @Slot()
    def refresh_configs(self):
        """Refresh configurations"""
        try:
            self.config_service.sync_configurations()
            self.load_configurations()
        except Exception as e:
            print(f"Error refreshing configurations: {e}")

    @Slot(str, str)
    def _on_live_config_change(self, key: str, value: str):
        """Immediately refresh table when a config changes via Socket.IO."""
        self.load_configurations()
    
    def show_success(self, message: str):
        """Show success message"""
        QMessageBox.information(self, "Success", message)
    
    def show_error(self, message: str):
        """Show error message"""
        QMessageBox.critical(self, "Error", message)
    
    def closeEvent(self, event):
        """Handle page close"""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        event.accept()
