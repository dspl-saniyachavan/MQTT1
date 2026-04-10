from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QFrame, QWidget)
from PySide6.QtCore import Qt, QEventLoop, QTimer
from PySide6.QtGui import QPixmap
import os
import sqlite3
import bcrypt

class LoginDialog(QDialog):
    """Login dialog window"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.user_data = None
        self.setup_ui()
    
    def setup_ui(self):
        """Setup login UI"""
        self.setWindowTitle("PrecisionPulse - Login")
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.showMaximized()
        
        # Dark background
        self.setStyleSheet("QDialog { background-color: #1e293b; }")
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Center container
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignCenter)
        
        # Login card
        card = QFrame()
        card.setMinimumSize(520, 700)
        card.setMaximumWidth(520)
        card.setStyleSheet("""
            QFrame {
                background-color: #f3f4f6;
                border-radius: 20px;
            }
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(15)
        card_layout.setContentsMargins(40, 40, 40, 40)
        
        # Logo
        logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'logo.svg')
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_label.setStyleSheet("background-color: transparent;")
        
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setFixedSize(100, 100)
        
        # Title
        title_label = QLabel("Welcome Back")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 42px;
                font-weight: 700;
                color: #1e293b;
                margin-top: 15px;
            }
        """)
        
        # Subtitle
        subtitle_label = QLabel("Sign in to PrecisionPulse")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                color: #64748b;
                margin-bottom: 15px;
            }
        """)
        
        # Email field
        email_label = QLabel("Email Address")
        email_label.setStyleSheet("font-weight: 600; color: #1e293b; font-size: 19px;")
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("admin@precisionpulse.com")
        self.email_input.setFixedHeight(52)
        self.email_input.setStyleSheet("""
            QLineEdit {
                padding: 0 16px;
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                font-size: 20px;
                background-color: white;
                color: #1e293b;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        
        # Password field
        password_label = QLabel("Password")
        password_label.setStyleSheet("font-weight: 600; color: #1e293b; font-size: 19px; margin-top: 5px;")
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setFixedHeight(52)
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 0 16px;
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                font-size: 20px;
                background-color: white;
                color: #1e293b;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        
        # Error message
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignLeft)
        self.error_label.setWordWrap(True)
        self.error_label.setMinimumHeight(0)
        self.error_label.setStyleSheet("""
            QLabel {
                color: #991b1b;
                background-color: #fee2e2;
                border-left: 4px solid #dc2626;
                border-radius: 6px;
                padding: 12px;
                font-size: 18px;
            }
        """)
        self.error_label.hide()
        
        # Sign In button
        self.login_button = QPushButton("Sign In")
        self.login_button.clicked.connect(self.handle_login)
        self.login_button.setFixedHeight(52)
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 700;
                font-size: 21px;
                margin-top: 5px;
            }
            QPushButton:hover {
                background-color: #6d28d9;
            }
            QPushButton:pressed {
                background-color: #5b21b6;
            }
        """)
        
        # Footer text
        footer_label = QLabel("New to PrecisionPulse?")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setStyleSheet("""
            QLabel {
                font-size: 19px;
                color: #64748b;
                margin-top: 15px;
            }
        """)
        
        contact_label = QLabel("Contact your administrator to create an account")
        contact_label.setAlignment(Qt.AlignCenter)
        contact_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                color: #94a3b8;
            }
        """)
        
        # Add widgets to card
        card_layout.addWidget(logo_label, 0, Qt.AlignCenter)
        card_layout.addWidget(title_label)
        card_layout.addWidget(subtitle_label)
        card_layout.addSpacing(10)
        card_layout.addWidget(email_label)
        card_layout.addWidget(self.email_input)
        card_layout.addWidget(password_label)
        card_layout.addWidget(self.password_input)
        card_layout.addWidget(self.error_label)
        card_layout.addWidget(self.login_button)
        card_layout.addSpacing(10)
        card_layout.addWidget(footer_label)
        card_layout.addWidget(contact_label)
        card_layout.addStretch()
        
        center_layout.addWidget(card, 0, Qt.AlignCenter)
        main_layout.addWidget(center_widget)
        
        # Connect Enter key to move to password field
        self.email_input.returnPressed.connect(self.password_input.setFocus)
        # Connect Enter key in password to login
        self.password_input.returnPressed.connect(self.handle_login)
    
    def handle_login(self):
        """Handle login attempt inside the same dialog"""
        email = self.email_input.text().strip()
        password = self.password_input.text()

        # Hide previous error
        self.error_label.hide()

        # Validate email
        if not email:
            self.show_error("Email Required", "Please enter your email address.")
            return

        if '@' not in email or '.' not in email.split('@')[-1]:
            self.show_error("Invalid Email", "Please enter a valid email address.")
            return

        # Validate password
        if not password:
            self.show_error("Password Required", "Please enter your password.")
            return

        # Attempt login via parent auth_service
        if self.parent() and hasattr(self.parent(), "auth_service"):
            # First try local SQLite
            if self.parent().auth_service.login(email, password):
                # Successful login → close dialog
                self.user_data = {'email': email, 'password': password}
                self.accept()
            else:
                # Local auth failed — try backend API to sync user first
                self.show_error(
                    "Syncing User",
                    "Attempting to sync user from backend..."
                )
                if self._sync_user_from_backend(email, password):
                    # User synced successfully — retry local login
                    if self.parent().auth_service.login(email, password):
                        self.user_data = {'email': email, 'password': password}
                        self.accept()
                    else:
                        self.show_error(
                            "Login Failed",
                            "User synced but local authentication failed."
                        )
                        self.email_input.clear()
                        self.password_input.clear()
                else:
                    # Backend sync failed
                    self.show_error(
                        "Login Failed",
                        "The email or password you entered is incorrect."
                    )
                    self.email_input.clear()
                    self.password_input.clear()
        else:
            # Fallback: auth service not found
            self.show_error(
                "Internal Error",
                "Authentication service not available."
            )
    
    def _sync_user_from_backend(self, email: str, password: str) -> bool:
        """Request user credentials from backend via MQTT and wait for response.
        Publishes to precisionpulse/sync/users/auth-request.
        Backend responds on precisionpulse/sync/users/auth-response.
        """
        try:
            from src.core.config import Config
            from src.core.encryption import encrypt_payload
            import json, uuid
            from datetime import datetime

            parent = self.parent()
            if not parent or not hasattr(parent, 'mqtt_service'):
                return False
            mqtt_svc = parent.mqtt_service
            if not mqtt_svc or not mqtt_svc.is_connected:
                return False

            request_id = str(uuid.uuid4())
            self._auth_response = None

            # Subscribe to response topic and listen
            def _on_message(topic, payload):
                if 'auth-response' not in topic:
                    return
                if '_enc' in payload:
                    try:
                        from src.core.encryption import decrypt_payload
                        payload = decrypt_payload(payload['_enc'])
                    except Exception:
                        return
                if payload.get('request_id') == request_id:
                    self._auth_response = payload

            mqtt_svc.message_received.connect(_on_message)
            mqtt_svc.client.subscribe('precisionpulse/sync/users/auth-response', qos=1)

            # Publish auth request (password hash sent encrypted)
            bcrypt_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            req_payload = {
                'type': 'auth_request',
                'request_id': request_id,
                'timestamp': datetime.now().isoformat(),
                'email': email,
                'password': password,  # backend verifies against PostgreSQL
            }
            try:
                encrypted = {'_enc': encrypt_payload(req_payload), 'type': 'auth_request'}
            except Exception:
                encrypted = req_payload

            mqtt_svc.client.publish(
                'precisionpulse/sync/users/auth-request',
                json.dumps(encrypted), qos=1
            )

            # Wait up to 5 seconds for response
            loop = QEventLoop()
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(loop.quit)
            timer.start(5000)

            def _check():
                if self._auth_response is not None:
                    loop.quit()
            poll = QTimer()
            poll.timeout.connect(_check)
            poll.start(100)
            loop.exec()
            poll.stop()
            timer.stop()
            mqtt_svc.message_received.disconnect(_on_message)

            resp = self._auth_response
            if not resp or not resp.get('success'):
                return False

            user = resp.get('user', {})
            db_path = Config.DATABASE_PATH
            if not os.path.isabs(db_path):
                app_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                db_path = os.path.join(app_dir, db_path)

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                password_hash = bcrypt.hashpw(
                    password.encode('utf-8'), bcrypt.gensalt()
                ).decode('utf-8')
                cursor.execute('''
                    INSERT OR REPLACE INTO users (id, email, name, password_hash, role, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user.get('id'), user.get('email'), user.get('name'),
                      password_hash, user.get('role', 'user'), 1))
                conn.commit()
            print(f'[LOGIN] Synced user {email} from backend via MQTT')
            return True
        except Exception as e:
            print(f'[LOGIN] MQTT sync error: {e}')
            return False
    
    def authenticate(self, email: str, password: str) -> bool:
        """User authentication - removed, handled by auth_service"""
        # This will be handled by auth_service in main_window
        self.user_data = {'email': email, 'password': password}
        return True
    
    def show_error(self, title: str, message: str):
        """Show error message with title"""
        error_text = f"<b style='color: #dc2626; font-size: 19px;'>✖ {title}</b><br/><span style='color: #991b1b; font-size: 18px;'>{message.replace(chr(10), '<br/>')}</span>"
        self.error_label.setText(error_text)
        self.error_label.setTextFormat(Qt.RichText)
        self.error_label.adjustSize()
        self.error_label.show()
    
    def get_user_data(self):
        """Get authenticated user data"""
        return self.user_data
# edit values fuctionality not working in web app- When value is modified, it automatically increase continuously by increments of 0.5 or 0.10.
# also in desktop app when alert is critical then change the color og current value only and show critical sign not change the whole card
# , User active/inactive status not properly showing in desktop
# in alert page add pagination,soting filtering,in profile page input field not working properly and disable the email field from both in desktop app alert ui is not displaying for set alert values to parameters
# In history page remove parameter stats field
# in web app do not render whole system at a time render only those which page is hitting
# Implement lazy loading for web app