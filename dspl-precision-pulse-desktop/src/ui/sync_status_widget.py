"""
Real-time synchronization status widget
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor
from datetime import datetime


class SyncStatusWidget(QWidget):
    """Widget showing real-time sync status with desktop clients"""
    
    def __init__(self, mqtt_service=None, user_sync_service=None):
        super().__init__()
        self.mqtt_service = mqtt_service
        self.user_sync_service = user_sync_service
        self.last_sync_time = None
        self.sync_count = 0
        
        self.setup_ui()
        self.connect_signals()
        
        # Blink timer for syncing state
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self._toggle_blink)
        self.blink_state = True
    
    def setup_ui(self):
        """Setup sync status UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # MQTT connection status
        self.mqtt_status = QLabel("● MQTT")
        self.mqtt_status.setStyleSheet("""
            QLabel {
                color: #dc2626;
                font-weight: 600;
                font-size: 12px;
                padding: 4px 8px;
                background-color: rgba(220, 38, 38, 0.1);
                border-radius: 4px;
            }
        """)
        
        # User sync status
        self.user_sync_status = QLabel("● Users")
        self.user_sync_status.setStyleSheet("""
            QLabel {
                color: #64748b;
                font-weight: 600;
                font-size: 12px;
                padding: 4px 8px;
                background-color: rgba(100, 116, 139, 0.1);
                border-radius: 4px;
            }
        """)
        
        # Last sync time
        self.last_sync_label = QLabel("Last sync: never")
        self.last_sync_label.setStyleSheet("""
            QLabel {
                color: #94a3b8;
                font-size: 11px;
                padding: 4px 8px;
            }
        """)
        
        layout.addWidget(self.mqtt_status)
        layout.addWidget(self.user_sync_status)
        layout.addWidget(self.last_sync_label)
        layout.addStretch()
    
    def connect_signals(self):
        """Connect to service signals"""
        if self.mqtt_service:
            self.mqtt_service.connected.connect(self._on_mqtt_connected)
            self.mqtt_service.disconnected.connect(self._on_mqtt_disconnected)
        
        if self.user_sync_service:
            self.user_sync_service.user_created.connect(self._on_user_synced)
            self.user_sync_service.user_updated.connect(self._on_user_synced)
            self.user_sync_service.user_deleted.connect(self._on_user_synced)
            self.user_sync_service.role_changed.connect(self._on_role_changed)
    
    def _on_mqtt_connected(self):
        """Handle MQTT connection"""
        self.mqtt_status.setText("● MQTT Connected")
        self.mqtt_status.setStyleSheet("""
            QLabel {
                color: #059669;
                font-weight: 600;
                font-size: 12px;
                padding: 4px 8px;
                background-color: rgba(5, 150, 105, 0.1);
                border-radius: 4px;
            }
        """)
        self.blink_timer.stop()
    
    def _on_mqtt_disconnected(self):
        """Handle MQTT disconnection"""
        self.mqtt_status.setText("● MQTT Disconnected")
        self.mqtt_status.setStyleSheet("""
            QLabel {
                color: #dc2626;
                font-weight: 600;
                font-size: 12px;
                padding: 4px 8px;
                background-color: rgba(220, 38, 38, 0.1);
                border-radius: 4px;
            }
        """)
    
    def _on_user_synced(self, *args):
        """Handle user sync event"""
        self.sync_count += 1
        self._update_sync_status()
        self._update_last_sync_time()
    
    def _on_role_changed(self, *args):
        """Handle role change event"""
        self.sync_count += 1
        self._update_sync_status()
        self._update_last_sync_time()
    
    def _update_sync_status(self):
        """Update user sync status indicator"""
        self.user_sync_status.setText(f"● Users Syncing ({self.sync_count})")
        self.user_sync_status.setStyleSheet("""
            QLabel {
                color: #f59e0b;
                font-weight: 600;
                font-size: 12px;
                padding: 4px 8px;
                background-color: rgba(245, 158, 11, 0.1);
                border-radius: 4px;
            }
        """)
        
        # Start blink animation
        self.blink_timer.start(500)
        
        # Reset after 3 seconds
        QTimer.singleShot(3000, self._reset_sync_status)
    
    def _reset_sync_status(self):
        """Reset sync status to idle"""
        self.blink_timer.stop()
        self.user_sync_status.setText("● Users Synced")
        self.user_sync_status.setStyleSheet("""
            QLabel {
                color: #059669;
                font-weight: 600;
                font-size: 12px;
                padding: 4px 8px;
                background-color: rgba(5, 150, 105, 0.1);
                border-radius: 4px;
            }
        """)
    
    def _toggle_blink(self):
        """Toggle blink state for syncing indicator"""
        self.blink_state = not self.blink_state
        if self.blink_state:
            self.user_sync_status.setStyleSheet("""
                QLabel {
                    color: #f59e0b;
                    font-weight: 600;
                    font-size: 12px;
                    padding: 4px 8px;
                    background-color: rgba(245, 158, 11, 0.1);
                    border-radius: 4px;
                }
            """)
        else:
            self.user_sync_status.setStyleSheet("""
                QLabel {
                    color: #f59e0b;
                    font-weight: 600;
                    font-size: 12px;
                    padding: 4px 8px;
                    background-color: rgba(245, 158, 11, 0.05);
                    border-radius: 4px;
                }
            """)
    
    def _update_last_sync_time(self):
        """Update last sync time label"""
        self.last_sync_time = datetime.now()
        time_str = self.last_sync_time.strftime("%H:%M:%S")
        self.last_sync_label.setText(f"Last sync: {time_str}")
