"""
User profile page - read-only display with local password change
"""

import os
import sqlite3
import logging
from argon2 import PasswordHasher
import bcrypt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QFrame, QScrollArea,
                               QMessageBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

_STYLE_FIELD_LABEL = "color: #94a3b8; font-size: 14px; font-weight: 500; background: transparent;"

from src.ui.CustomMessageBox import CustomMessageBox

logger = logging.getLogger(__name__)
ph = PasswordHasher()


class ProfilePage(QWidget):
    """User profile page widget"""

    back_clicked = Signal()

    def __init__(self, user_data=None, sync_service=None):
        super().__init__()
        self.user_data = user_data or {}
        self.sync_service = sync_service

    def set_user_data(self, user_data):
        """Set user data and rebuild UI"""
        self.user_data = user_data or {}
        self.setup_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.layout():
            self.setup_ui()

    def setup_ui(self):
        """Setup profile UI"""
        # Clear existing layout
        old = self.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            QWidget().setLayout(old)

        self.setStyleSheet("background-color: #1e293b;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.create_header(layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: #1e293b; }
            QScrollBar:vertical { background: #334155; width: 10px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #475569; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #64748b; }
        """)

        content = QWidget()
        content.setStyleSheet("background-color: #1e293b;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 40, 0, 40)
        content_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        content_layout.addWidget(self.create_profile_card())
        content_layout.addSpacing(24)
        content_layout.addWidget(self.create_password_card())
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def create_header(self, layout):
        header = QFrame()
        header.setFixedHeight(90)
        header.setStyleSheet("background-color: #334155; border: none;")

        h = QHBoxLayout(header)
        h.setContentsMargins(30, 0, 30, 0)

        logo = QLabel()
        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'assets', 'logo.svg')
        if os.path.exists(logo_path):
            px = QPixmap(logo_path)
            logo.setPixmap(px.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo.setStyleSheet("background-color: transparent;")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(50, 50)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        t = QLabel("PrecisionPulse")
        t.setStyleSheet("color: white; font-size: 22px; font-weight: 700; background: transparent;")
        s = QLabel("Profile")
        s.setStyleSheet("color: #94a3b8; font-size: 14px; background: transparent;")
        title_col.addWidget(t)
        title_col.addWidget(s)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(15)
        logo_row.addWidget(logo)
        logo_row.addLayout(title_col)

        h.addLayout(logo_row)
        h.addStretch()

        back_btn = QPushButton("Back to Dashboard")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; color: white; border: none;
                border-radius: 8px; padding: 12px 24px;
                font-weight: 600; font-size: 14px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        back_btn.clicked.connect(self.back_clicked.emit)
        h.addWidget(back_btn)
        layout.addWidget(header)

    def create_profile_card(self):
        card = QFrame()
        card.setFixedWidth(640)
        card.setStyleSheet("""
            QFrame { background-color: #1e293b; border-radius: 16px; border: 1px solid #334155; }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        title = QLabel("Profile Information")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: 700; background: transparent;")
        layout.addWidget(title)

        field_style = """
            QLineEdit {
                background-color: #0f172a; color: white; border: 1px solid #334155;
                border-radius: 8px; padding: 12px 14px; font-size: 14px;
            }
            QLineEdit:focus { border-color: #6366f1; }
        """

        # Name field (editable)
        name_lbl = QLabel("Full Name")
        name_lbl.setStyleSheet(_STYLE_FIELD_LABEL)
        layout.addWidget(name_lbl)
        self.name_field = QLineEdit(self.user_data.get('name', ''))
        self.name_field.setStyleSheet(field_style)
        layout.addWidget(self.name_field)

        # Email (read-only)
        email_lbl = QLabel("Email")
        email_lbl.setStyleSheet(_STYLE_FIELD_LABEL)
        layout.addWidget(email_lbl)
        email_val = QLineEdit(self.user_data.get('email', ''))
        email_val.setReadOnly(True)
        email_val.setStyleSheet(field_style + "QLineEdit { color: #94a3b8; }")
        layout.addWidget(email_val)

        role_lbl = QLabel("Role")
        role_lbl.setStyleSheet(_STYLE_FIELD_LABEL)
        layout.addWidget(role_lbl)

        badge = QLabel(self.user_data.get('role', 'user').upper())
        badge.setStyleSheet("""
            background-color: #4f46e5; color: white;
            font-size: 11px; font-weight: 700;
            padding: 5px 14px; border-radius: 6px;
        """)
        badge.setFixedWidth(90)
        layout.addWidget(badge)

        save_btn = QPushButton("Save Profile")
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #4f46e5,stop:1 #6366f1);
                color: white; border: none; border-radius: 8px;
                padding: 12px; font-weight: 600; font-size: 14px;
            }
            QPushButton:hover { background: #4338ca; }
        """)
        save_btn.clicked.connect(self._save_profile)
        layout.addWidget(save_btn)

        return card

    def _save_profile(self):
        """Save name change to SQLite and publish to backend via MQTT."""
        new_name = self.name_field.text().strip()
        if not new_name:
            CustomMessageBox("Warning", "Name cannot be empty.").exec()
            return
        email = self.user_data.get('email', '')
        try:
            db_path = "data/precision_pulse.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("UPDATE users SET name=?, updated_at=datetime('now','localtime') WHERE email=?",
                             (new_name, email))
                conn.commit()
            self.user_data['name'] = new_name
            if self.sync_service and hasattr(self.sync_service, 'publish'):
                self.sync_service.publish('precisionpulse/sync/users/updated', {
                    'type': 'user_updated',
                    'user': {'email': email, 'name': new_name,
                             'role': self.user_data.get('role', 'user'),
                             'is_active': True}
                })
            CustomMessageBox("Success", "Profile updated successfully!").exec()
        except Exception as e:
            CustomMessageBox("Error", f"Failed to update profile: {e}").exec()

    def create_password_card(self):
        card = QFrame()
        card.setFixedWidth(640)
        card.setStyleSheet("""
            QFrame { background-color: #1e293b; border-radius: 16px; border: 1px solid #334155; }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        title = QLabel("Change Password")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: 700; background: transparent;")
        layout.addWidget(title)

        field_style = """
            QLineEdit {
                background-color: #0f172a; color: white; border: 1px solid #334155;
                border-radius: 8px; padding: 12px 14px; font-size: 14px;
            }
            QLineEdit:focus { border-color: #6366f1; }
        """

        for attr, label in [
            ('current_password', 'Current Password'),
            ('new_password',     'New Password'),
            ('confirm_password', 'Confirm New Password'),
        ]:
            lbl = QLabel(label)
            lbl.setStyleSheet(_STYLE_FIELD_LABEL)
            layout.addWidget(lbl)
            field = QLineEdit()
            field.setEchoMode(QLineEdit.Password)
            field.setStyleSheet(field_style)
            setattr(self, attr, field)
            layout.addWidget(field)

        btn = QPushButton("Update Password")
        btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; color: white; border: none;
                border-radius: 8px; padding: 14px;
                font-weight: 600; font-size: 16px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        btn.clicked.connect(self.update_password)
        layout.addWidget(btn)

        return card

    def _remove_avatar(self):
        """Remove profile picture from local DB and publish via MQTT."""
        try:
            db_path = "data/precision_pulse.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("UPDATE users SET avatar_url=NULL WHERE email=?",
                             (self.user_data.get('email'),))
                conn.commit()
            self.user_data['avatar_url'] = None
            if self.sync_service and hasattr(self.sync_service, 'publish'):
                self.sync_service.publish('precisionpulse/sync/users/updated', {
                    'type': 'user_updated',
                    'user': {'email': self.user_data.get('email'), 'avatar_url': None,
                             'name': self.user_data.get('name'),
                             'role': self.user_data.get('role', 'user'), 'is_active': True}
                })
            CustomMessageBox("Success", "Profile picture removed.").exec()
            self.setup_ui()
        except Exception as e:
            CustomMessageBox("Error", f"Failed to remove picture: {e}").exec()

    def update_password(self):
        cur  = self.current_password.text().strip()
        new  = self.new_password.text().strip()
        conf = self.confirm_password.text().strip()

        if not cur:
            CustomMessageBox("Warning", "The current password cannot be empty").exec()
            return
        if not new:
            CustomMessageBox("Warning", "The new password cannot be empty").exec()
            return
        if not conf:
            CustomMessageBox("Warning", "Confirm password cannot be empty.").exec()
            return
        if cur == new:
            CustomMessageBox("Warning", "New password is same as current.").exec()
            return
        if new != conf:
            CustomMessageBox("Warning", "New password does not match the confirm password.").exec()
            return

        db_path = "data/precision_pulse.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT password_hash FROM users WHERE email = ?",
                (self.user_data.get('email'),)
            )
            row = cursor.fetchone()
            if not row:
                CustomMessageBox("Error", "User not found in database").exec()
                return

            stored_hash = row[0]
            try:
                if stored_hash.startswith('$2b$'):
                    if not bcrypt.checkpw(cur.encode('utf-8'), stored_hash.encode('utf-8')):
                        CustomMessageBox("Error", "Current password is incorrect").exec()
                        return
                else:
                    ph.verify(stored_hash, cur)
            except Exception:
                CustomMessageBox("Error", "Current password is incorrect").exec()
                return

            new_hash = bcrypt.hashpw(new.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute(
                "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE email = ?",
                (new_hash, self.user_data.get('email'))
            )
            conn.commit()

            self._sync_password_to_backend(new_hash, current_password=cur)

            CustomMessageBox("Success", "Password updated successfully!").exec()
            self.current_password.clear()
            self.new_password.clear()
            self.confirm_password.clear()

        except Exception as e:
            logger.error(f"[PASSWORD] Error updating password: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")
        finally:
            conn.close()

    def _sync_password_to_backend(self, password_hash: str, current_password: str = ''):
        """Publish password change to backend via MQTT."""
        if self.sync_service and hasattr(self.sync_service, 'publish'):
            self.sync_service.publish('precisionpulse/sync/users/password-changed', {
                'type': 'user_password_changed',
                'email': self.user_data.get('email'),
                'password_hash': password_hash,
                'current_password': current_password,
            })
            logger.info('[PASSWORD] Published password change via MQTT')
            return True
        return False
