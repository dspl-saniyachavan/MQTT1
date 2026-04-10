"""
Main window for PrecisionPulse Desktop Application
"""

import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QFrame, QStackedWidget,
                               QMessageBox, QScrollArea, QSizePolicy, QSpacerItem)
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QPixmap
from src.ui.login_dialog import LoginDialog
from src.ui.telemetry_widget import TelemetryWidget
from src.ui.parameters_page import ParametersPage
from src.ui.profile_page import ProfilePage
from src.ui.manage_users_page import ManageUsersPage
from src.ui.sync_status_widget import SyncStatusWidget
from src.ui.modern_datetime_widget import ModernDateTimeWidget
from src.ui.configuration_page import ConfigurationPage
from src.ui.history_page import HistoryPage
from src.services.mqtt_service import MQTTService
from src.services.mqtt_factory import MQTTClientFactory
from src.services.mqtt_broker import MQTTBroker
from src.services.telemetry_service import TelemetryService
from src.services.sync_service import SyncService
from src.services.parameter_sync_service import ParameterSyncService
from src.services.user_sync_service import UserSyncService
from src.services.configuration_service import ConfigurationService
from src.services.config_socketio_handler import setup_config_handlers
from src.services.command_executor import CommandExecutor
from src.services.parameter_stream_sync_service import ParameterStreamSyncService  # kept for offline MQTT buffer flush
from src.core.database import DatabaseManager
from src.core.router import Router
from src.core.auth_service import AuthService
from src.core.rbac import RoleBasedAccessControl
import uuid
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QDialog

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.device_id = str(uuid.uuid4())
        self.header_btn_layout = None  # Store reference to button layout
        
        # Initialize database
        self.db = DatabaseManager()
        self.db.initialize_database()
        
        # Initialize auth service
        self.auth_service = AuthService(self.db)
        self.auth_service.user_logged_in.connect(self.on_user_logged_in)
        self.auth_service.user_logged_out.connect(self.on_user_logged_out)
        self.auth_service.session_expired.connect(self.on_session_expired)
        
        # Initialize router
        self.router = Router()
        self.router.route_changed.connect(self.on_route_changed)
        self.router.unauthorized_access.connect(self.on_unauthorized_access)
        
        # Initialize services (connect to backend MQTT broker)
        mqtt_client = MQTTClientFactory.create_client(self.device_id)
        self.mqtt_service = MQTTService(self.device_id, mqtt_client)
        
        # Import parameter sync service
        self.parameter_sync_service = ParameterSyncService(mqtt_service=self.mqtt_service)
        self.parameter_sync_service.set_db_path(self.db.db_path)
        self.mqtt_service.message_received.connect(self.parameter_sync_service._on_mqtt_message)
        self.parameter_sync_service.parameter_updated.connect(self._on_parameter_synced)
        
        # Import user sync service
        self.user_sync_service = UserSyncService(mqtt_service=self.mqtt_service, database_manager=self.db)
        self.mqtt_service.message_received.connect(self.user_sync_service._on_mqtt_message)
        self.mqtt_service.message_received.connect(self._on_presence_message)
        
        # Config service — initialize before telemetry service
        self.config_service = ConfigurationService(self.db, self.auth_service)
        # NOTE: load_local_configs() is called in on_user_logged_in after all
        # callbacks are registered, so persisted values are applied immediately.

        # Telemetry service with config service for dynamic interval updates
        self.telemetry_service = TelemetryService(self.mqtt_service, self.db, self.parameter_sync_service, self.config_service)
        self.sync_service = SyncService(self.mqtt_service, self.db)

        # Setup config handlers and start sync
        setup_config_handlers(self.mqtt_service, self.config_service)
        self.config_service.start_sync_thread()
        self.config_service.register_callback('MAX_CHART_DATA_POINTS', self._on_max_chart_points_changed)

        # Command executor — receives MQTT commands from web and sends ACKs back
        self.command_executor = CommandExecutor(
            self.mqtt_service,
            self.config_service,
            self.user_sync_service
        )
        
        # Connect user sync service signals
        self.user_sync_service.user_created.connect(self._on_user_created)
        self.user_sync_service.user_updated.connect(self._on_user_updated)
        self.user_sync_service.user_deleted.connect(self._on_user_deleted)
        self.user_sync_service.role_changed.connect(self._on_role_changed)
        
        # Connect telemetry service signals
        self.telemetry_service.connection_status_changed.connect(self._on_telemetry_status_changed)
        self.telemetry_service.buffered_data_synced.connect(self._on_buffered_data_synced)
        
        # Also connect MQTT service signals directly for immediate updates
        self.mqtt_service.connected.connect(lambda: self.update_connection_status(True))
        self.mqtt_service.disconnected.connect(lambda: self.update_connection_status(False))
        
        # Connect sync service signals
        self.sync_service.user_synced.connect(self._on_user_synced)
        self.sync_service.parameter_synced.connect(self._on_parameter_synced)
        
        # Setup parameter refresh timer
        self.parameter_refresh_timer = QTimer()
        self.parameter_refresh_timer.timeout.connect(self._refresh_parameters)
        self.parameter_refresh_timer.start(10000)  # Refresh every 10 seconds
        
        # Show login first
        if not self.show_login():
            import sys
            sys.exit(0)
        
        # Setup UI after successful login
        self.setup_ui()
        self.setup_routes()
        self.setStyleSheet("QMainWindow{background:#0f172a;}")
    
    def setup_ui(self):
        """Setup the main UI with sidebar + top navbar"""
        self.setWindowTitle("PrecisionPulse Desktop")
        screen = self.screen().availableGeometry()
        self.resize(int(screen.width() * 0.95), int(screen.height() * 0.95))
        self.move(screen.center() - self.rect().center())

        root_widget = QWidget()
        root_widget.setStyleSheet("background:#0f172a;")
        self.setCentralWidget(root_widget)
        root_vbox = QVBoxLayout(root_widget)
        root_vbox.setContentsMargins(0, 0, 0, 0)
        root_vbox.setSpacing(0)

        # ── Top navbar ────────────────────────────────────────────────────────
        navbar = QFrame()
        navbar.setFixedHeight(56)
        navbar.setStyleSheet("background:#1e293b;border-bottom:1px solid #334155;")
        nav_hl = QHBoxLayout(navbar)
        nav_hl.setContentsMargins(20, 0, 20, 0)
        nav_hl.setSpacing(12)

        nav_title = QLabel("PrecisionPulse")
        nav_title.setStyleSheet("color:white;font-size:16px;font-weight:700;background:transparent;")
        nav_hl.addWidget(nav_title)
        nav_hl.addStretch()

        self.connected_label = QLabel("● Disconnected")
        self.connected_label.setStyleSheet(
            "color:#fca5a5;font-size:12px;font-weight:600;"
            "background:rgba(220,38,38,0.15);border:1px solid rgba(220,38,38,0.3);"
            "border-radius:6px;padding:4px 12px;"
        )
        nav_hl.addWidget(self.connected_label)

        self.mqtt_toggle_btn = QPushButton("▶ Start MQTT")
        self.mqtt_toggle_btn.setStyleSheet(
            "QPushButton{background:rgba(5,150,105,0.20);color:#86efac;"
            "border:1px solid rgba(5,150,105,0.4);border-radius:6px;"
            "padding:6px 14px;font-weight:600;font-size:12px;}"
            "QPushButton:hover{background:rgba(5,150,105,0.35);}"
        )
        self.mqtt_toggle_btn.clicked.connect(self.toggle_mqtt)
        nav_hl.addWidget(self.mqtt_toggle_btn)
        root_vbox.addWidget(navbar)
        # Sync button state with actual MQTT connection state after UI is built
        QTimer.singleShot(0, lambda: self.update_connection_status(self.mqtt_service.is_connected))

        # ── Body: sidebar + stacked pages ─────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background:#0f172a;")
        body_hl = QHBoxLayout(body)
        body_hl.setContentsMargins(0, 0, 0, 0)
        body_hl.setSpacing(0)
        root_vbox.addWidget(body, 1)

        self.sidebar = self._create_sidebar()
        self._build_nav_items()
        self._update_nav_active("dashboard")
        body_hl.addWidget(self.sidebar)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background:#0f172a;")
        body_hl.addWidget(self.stacked_widget, 1)

        # Pages
        self.telemetry_widget = TelemetryWidget(self.telemetry_service, self.auth_service)
        self.stacked_widget.addWidget(self.telemetry_widget)       # 0

        self.parameters_page = ParametersPage(self.db, self.auth_service, self.sync_service, self.parameter_sync_service)
        self.parameters_page.back_clicked.connect(lambda: self.router.navigate("dashboard"))
        self.parameters_page.parameters_changed.connect(self.on_parameters_changed)
        self.stacked_widget.addWidget(self.parameters_page)        # 1

        self.profile_page = ProfilePage(self.auth_service.get_current_user(), sync_service=self.user_sync_service)
        self.profile_page.back_clicked.connect(lambda: self.router.navigate("dashboard"))
        self.profile_page.setup_ui()
        self.stacked_widget.addWidget(self.profile_page)           # 2

        self.manage_users_page = ManageUsersPage(self.db, self.auth_service, self.user_sync_service)
        self.manage_users_page.back_clicked.connect(lambda: self.router.navigate("dashboard"))
        self.stacked_widget.addWidget(self.manage_users_page)      # 3

        self.configuration_page = ConfigurationPage(self.db, self.auth_service, self.config_service)
        self.configuration_page.back_clicked.connect(lambda: self.router.navigate("dashboard"))
        self.stacked_widget.addWidget(self.configuration_page)     # 4

        self.history_page = HistoryPage(self.db, self.auth_service,
                                        back_signal=lambda: self.router.navigate("dashboard"))
        self.stacked_widget.addWidget(self.history_page)           # 5

    def _create_sidebar(self) -> QFrame:
        """Build the left sidebar."""
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        # Use direct background color — no #objectName selector to avoid scoping issues
        sidebar.setStyleSheet(
            "background:#1e293b;"
            "border-right:1px solid #334155;"
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo block
        logo_frame = QFrame()
        logo_frame.setFixedHeight(72)
        logo_frame.setStyleSheet(
            "background:#1e293b;"
            "border-bottom:1px solid #334155;"
        )
        logo_hl = QHBoxLayout(logo_frame)
        logo_hl.setContentsMargins(16, 0, 16, 0)
        logo_hl.setSpacing(10)

        icon_lbl = QLabel("⚡")
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            "color:white;font-size:18px;"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #4f46e5,stop:1 #6366f1);"
            "border-radius:8px;"
        )
        logo_hl.addWidget(icon_lbl)

        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(0)
        t1 = QLabel("PrecisionPulse")
        t1.setStyleSheet("color:white;font-size:14px;font-weight:700;background:transparent;")
        t2 = QLabel("Telemetry")
        t2.setStyleSheet("color:#94a3b8;font-size:11px;background:transparent;")
        text_vbox.addWidget(t1)
        text_vbox.addWidget(t2)
        logo_hl.addLayout(text_vbox)
        layout.addWidget(logo_frame)

        # Nav scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea{border:none;background:#1e293b;}"
            "QScrollBar:vertical{width:0px;}"
        )
        nav_widget = QWidget()
        nav_widget.setStyleSheet("background:#1e293b;")
        self._nav_layout = QVBoxLayout(nav_widget)
        self._nav_layout.setContentsMargins(10, 16, 10, 16)
        self._nav_layout.setSpacing(2)
        self._nav_layout.addStretch()
        scroll.setWidget(nav_widget)
        layout.addWidget(scroll, 1)

        # Logout button at bottom
        logout_frame = QFrame()
        logout_frame.setStyleSheet(
            "background:#1e293b;"
            "border-top:1px solid #334155;"
        )
        logout_vbox = QVBoxLayout(logout_frame)
        logout_vbox.setContentsMargins(10, 10, 10, 14)

        logout_btn = QPushButton("  Logout")
        logout_btn.setFixedHeight(40)
        logout_btn.setStyleSheet(
            "QPushButton{background:#dc2626;color:white;border:none;"
            "border-radius:8px;padding:8px 16px;font-weight:600;font-size:13px;text-align:left;}"
            "QPushButton:hover{background:#b91c1c;}"
        )
        logout_btn.clicked.connect(self.logout)
        logout_vbox.addWidget(logout_btn)
        layout.addWidget(logout_frame)

        return sidebar

    _NAV_ITEMS = [
        ("Dashboard",    "dashboard",     "⊞",  False),
        ("Parameters",   "parameters",    "⚙",  False),
        ("Users",        "manage_users",  "👥",  True),
        ("History",      "history",       "📈",  False),
        ("Config",       "configuration", "🔧",  True),
        ("Profile",      "profile",       "👤",  False),
    ]

    def _build_nav_items(self):
        """Populate sidebar nav buttons for the current user role."""
        # Clear existing items (keep stretch at end)
        while self._nav_layout.count() > 1:
            item = self._nav_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        current_user = self.auth_service.get_current_user() if self.auth_service else None
        user_role = (current_user or {}).get('role', 'user')
        is_admin = user_role == 'admin'

        self._nav_btns = {}
        for label, route, icon, admin_only in self._NAV_ITEMS:
            if admin_only and not is_admin:
                continue
            btn = self._make_nav_btn(label, icon, route)
            self._nav_layout.insertWidget(self._nav_layout.count() - 1, btn)
            self._nav_btns[route] = btn

    def _make_nav_btn(self, label: str, icon: str, route: str) -> QPushButton:
        btn = QPushButton(f"  {icon}  {label}")
        btn.setFixedHeight(44)
        btn.setStyleSheet(self._nav_btn_style(active=False))
        btn.clicked.connect(lambda checked=False, r=route: self.router.navigate(r))
        return btn

    def _nav_btn_style(self, active: bool) -> str:
        if active:
            return (
                "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                "stop:0 #4f46e5,stop:1 #6366f1);"
                "color:white;border:none;border-radius:8px;"
                "padding:10px 16px;font-weight:600;font-size:13px;text-align:left;}"
            )
        return (
            "QPushButton{background:transparent;color:#94a3b8;border:none;"
            "border-radius:8px;padding:10px 16px;font-size:13px;text-align:left;}"
            "QPushButton:hover{background:rgba(51,65,85,0.5);color:white;}"
        )

    def _update_nav_active(self, active_route: str):
        for route, btn in getattr(self, '_nav_btns', {}).items():
            btn.setStyleSheet(self._nav_btn_style(active=(route == active_route)))
    
    def setup_routes(self):
        """Setup application routes"""
        self.router.register_route('dashboard',    lambda: self.stacked_widget.widget(0), requires_auth=True)
        self.router.register_route('parameters',   lambda: self.stacked_widget.widget(1), requires_auth=True)
        self.router.register_route('profile',      lambda: self.stacked_widget.widget(2), requires_auth=True)
        self.router.register_route('manage_users', lambda: self.stacked_widget.widget(3), requires_auth=True, allowed_roles=['admin'])
        self.router.register_route('configuration',lambda: self.stacked_widget.widget(4), requires_auth=True, allowed_roles=['admin'])
        self.router.register_route('history',      lambda: self.stacked_widget.widget(5), requires_auth=True)
        self.router.navigate('dashboard')
    
    def show_login(self):
        """Show login dialog"""
        login_dialog = LoginDialog(self)
        result = login_dialog.exec()
        return result == QDialog.DialogCode.Accepted
    
    def show_error(self, title: str, message: str):
        error_text = f"<b style='color: #dc2626; font-size: 19px;'>✖ {title}</b><br/><span style='color: #991b1b; font-size: 18px;'>{message.replace(chr(10), '<br/>')}</span>"
        self.error_label.setText(error_text)
        self.error_label.setTextFormat(Qt.RichText)
        self.error_label.adjustSize()
        self.error_label.show()
    
    def show_login_error(self, title, message):
        """Show an error message box for failed login"""
        error_message = QMessageBox(self)
        error_message.setIcon(QMessageBox.Critical)  # Critical icon for error
        error_message.setWindowTitle(title)  # Set the title of the message box
        error_message.setText(message)  # Set the error message text
        error_message.setStandardButtons(QMessageBox.Ok)  # Only "Ok" button
        error_message.exec()  # Show the message box
    
    def on_route_changed(self, route_name: str):
        """Handle route changes"""
        route_map = {
            'dashboard': 0, 'parameters': 1, 'profile': 2,
            'manage_users': 3, 'configuration': 4, 'history': 5,
        }
        if route_name in route_map:
            self.stacked_widget.setCurrentIndex(route_map[route_name])
            self._update_nav_active(route_name)
            if route_name == 'profile':
                self.profile_page.set_user_data(self.auth_service.get_current_user())
            elif route_name == 'manage_users':
                # Ensure current user is always shown as online
                current = self.auth_service.get_current_user()
                if current and current.get('email'):
                    self.manage_users_page.set_user_online(current['email'], True)
                self.manage_users_page.load_users()
            elif route_name == 'configuration':
                self.configuration_page.load_configs()
            elif route_name == 'history':
                self.history_page._load()
    
    def on_user_logged_in(self, user: dict):
        """Handle user login - start telemetry after MQTT connects"""
        self.router.set_user(user)
        self.config_service.load_local_configs()
        print(f" Starting MQTT connection for user: {user.get('name')}")
        self.mqtt_service.connect()
        # Mark current user as online in manage_users_page immediately
        if hasattr(self, 'manage_users_page'):
            self.manage_users_page.set_user_online(user.get('email', ''), True)
        # Publish online presence after MQTT connects (2 s delay)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.mqtt_service.publish_user_presence(
            user.get('email', ''), 'online'
        ))
    
    def _start_telemetry(self):
        """Start telemetry after broker is ready"""
        self.telemetry_service.start_streaming(3)
        self.update_connection_status(True)
    
    def on_user_logged_out(self):
        """Handle user logout - stop telemetry"""
        self.router.set_user(None)
        # Publish offline presence before disconnecting
        current = self.auth_service.get_current_user()
        if current:
            self.mqtt_service.publish_user_presence(current.get('email', ''), 'offline')
        self.telemetry_service.stop_streaming()
        self.close()
        if self.show_login():
            self.setup_ui()
            self.setup_routes()
            self.show()
        else:
            import sys
            sys.exit(0)
    
    def on_session_expired(self):
        """Handle session expiration"""
        QMessageBox.warning(self, "Session Expired", "Your session has expired. Please login again.")
        self.on_user_logged_out()
    
    def on_unauthorized_access(self):
        """Handle unauthorized access attempt"""
        QMessageBox.warning(self, "Access Denied", "You don't have permission to access this page.")
    
    def logout(self):
        """Handle user logout — stop MQTT (heartbeat stops, backend detects offline)."""
        self.auth_service.logout()
    
    def _on_telemetry_status_changed(self, connected: bool):
        """Handle telemetry status change"""
        self.update_connection_status(connected)
    
    def toggle_mqtt(self):
        """Start or stop the MQTT connection.
        STOP: disconnect MQTT only. push_timer keeps running so data generation
              continues — _push_data routes to local_buffer when is_connected=False.
        START: reconnect MQTT. On connect, local_buffer is flushed automatically.
        """
        if self.mqtt_service.is_connected:
            # ── STOP ──────────────────────────────────────────────────────────
            print("[UI] Stopping MQTT — data generation continues, routing to local_buffer")
            # Mark disconnected so _push_data writes to local_buffer
            self.telemetry_service.is_connected = False
            # Stop heartbeat only — push_timer keeps running for continuous generation
            self.telemetry_service.heartbeat_timer.stop()
            # Physically disconnect from broker
            self.mqtt_service.disconnect()
            # Update UI
            self.update_connection_status(False)
            # Backend detects offline via MQTT subscriber disconnect event
            print("[UI] MQTT stopped — data buffering to local_buffer")
        else:
            # ── START ─────────────────────────────────────────────────────────
            print("[UI] Starting MQTT connection")
            self.mqtt_service.connect()
            # _on_mqtt_connected will flush local_buffer and restart heartbeat
            self.update_connection_status(False)  # show connecting state

    def update_connection_status(self, connected: bool):
        """Update navbar connection status label and MQTT toggle button."""
        if hasattr(self, 'connected_label'):
            if connected:
                self.connected_label.setText("● Connected")
                self.connected_label.setStyleSheet(
                    "color:#86efac;font-size:12px;font-weight:600;"
                    "background:rgba(5,150,105,0.15);border:1px solid rgba(5,150,105,0.3);"
                    "border-radius:6px;padding:4px 12px;"
                )
            else:
                self.connected_label.setText("● Disconnected")
                self.connected_label.setStyleSheet(
                    "color:#fca5a5;font-size:12px;font-weight:600;"
                    "background:rgba(220,38,38,0.15);border:1px solid rgba(220,38,38,0.3);"
                    "border-radius:6px;padding:4px 12px;"
                )
        if hasattr(self, 'mqtt_toggle_btn'):
            if connected:
                self.mqtt_toggle_btn.setText(" Stop MQTT")
                self.mqtt_toggle_btn.setStyleSheet(
                    "QPushButton{background:rgba(220,38,38,0.20);color:#fca5a5;"
                    "border:1px solid rgba(220,38,38,0.4);border-radius:6px;"
                    "padding:6px 14px;font-weight:600;font-size:12px;}"
                    "QPushButton:hover{background:rgba(220,38,38,0.35);}"
                )
            else:
                self.mqtt_toggle_btn.setText("Start MQTT")
                self.mqtt_toggle_btn.setStyleSheet(
                    "QPushButton{background:rgba(5,150,105,0.20);color:#86efac;"
                    "border:1px solid rgba(5,150,105,0.4);border-radius:6px;"
                    "padding:6px 14px;font-weight:600;font-size:12px;}"
                    "QPushButton:hover{background:rgba(5,150,105,0.35);}"
                )
    
    @Slot(int)
    def _on_buffered_data_synced(self, count: int):
        """Handle buffered data sync completion"""
        pass
    
    @Slot()
    def on_parameters_changed(self):
        """Handle parameters configuration change"""
        # Refresh telemetry widget to show only enabled parameters
        if hasattr(self, 'telemetry_widget'):
            self.telemetry_widget.refresh_parameters()
    
    @Slot(dict)
    def _on_user_synced(self, user):
        """Handle user sync from remote"""
        # Reload users in manage users page if visible
        if self.router.get_current_route() == 'manage_users':
            self.manage_users_page.load_users()
    
    @Slot(dict)
    def _on_parameter_synced(self, parameter):
        """Handle parameter sync from remote - runs in main thread"""
        try:
            print(f" Parameter synced: {parameter.get('name', 'unknown')}")
            # Refresh telemetry service parameters
            if hasattr(self, 'telemetry_service'):
                self.telemetry_service.refresh_parameters()
            # Refresh telemetry widget silently (no popup)
            if hasattr(self, 'telemetry_widget'):
                self.telemetry_widget.refresh_parameters_silent()
            # Don't refresh parameters page here - it handles its own refresh
        except Exception as e:
            print(f"Error handling parameter sync: {e}")
    
    def _on_broker_started(self):
        """Handle broker startup"""
        pass
    
    def _on_broker_error(self, error: str):
        """Handle broker errors"""
        pass
    
    def _refresh_parameters(self):
        """Refresh parameters from backend and update dashboard"""
        if hasattr(self, 'telemetry_widget'):
            self.telemetry_widget.refresh_parameters()
    
    def _on_presence_message(self, topic: str, payload: dict):
        """Handle MQTT presence messages to update user online status."""
        if 'presence' not in topic:
            return
        email = payload.get('email', '')
        status = payload.get('status', 'online')
        if not email:
            return
        if hasattr(self, 'manage_users_page'):
            self.manage_users_page.set_user_online(email, status == 'online')

    def closeEvent(self, event):
        """Handle window close event — MQTT disconnect signals backend automatically."""
        if hasattr(self, 'parameter_refresh_timer'):
            self.parameter_refresh_timer.stop()
        event.accept()
    
    def _on_user_created(self, user: dict):
        """Handle user created event"""
        print(f"[UI] User created: {user.get('email')}")
        if self.router.get_current_route() == 'manage_users':
            self.manage_users_page.load_users()
    
    def _on_user_updated(self, user: dict):
        """Handle user updated event"""
        print(f"[UI] User updated: {user.get('email')}")
        # If the updated user is the currently logged-in user, refresh in-memory data and profile page
        current = self.auth_service.get_current_user()
        if current and current.get('id') == user.get('id'):
            current['name'] = user.get('name', current.get('name'))
            current['email'] = user.get('email', current.get('email'))
            current['role'] = user.get('role', current.get('role'))
            self.profile_page.set_user_data(current)
            if hasattr(self, 'telemetry_widget'):
                self.telemetry_widget.update_user_name(current['name'])
        if self.router.get_current_route() == 'manage_users':
            self.manage_users_page.load_users()
    
    def _on_user_deleted(self, user_id: int, email: str):
        """Handle user deleted event"""
        print(f"[UI] User deleted: {email}")
        if self.router.get_current_route() == 'manage_users':
            self.manage_users_page.load_users()
    
    def _on_role_changed(self, user_id: int, email: str, old_role: str, new_role: str):
        """Handle role changed event"""
        print(f"[UI] Role changed for {email}: {old_role} -> {new_role}")
        if self.router.get_current_route() == 'manage_users':
            self.manage_users_page.load_users()
    
    def _on_max_chart_points_changed(self, key: str, new_value, old_value):
        """Forward MAX_CHART_DATA_POINTS change to telemetry widget."""
        try:
            if hasattr(self, 'telemetry_widget'):
                self.telemetry_widget.apply_max_chart_points(int(new_value))
        except Exception as e:
            print(f"[UI] Error applying MAX_CHART_DATA_POINTS: {e}")
