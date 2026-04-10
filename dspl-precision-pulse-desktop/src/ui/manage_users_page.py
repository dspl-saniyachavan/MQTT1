"""
Manage Users page for admin
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QFrame, QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QDialog, QLineEdit, QComboBox, QMessageBox)
from PySide6.QtCore import Qt, Signal, QTimer, Slot
from PySide6.QtGui import QPixmap
from typing import Dict
import os

from src.ui.CustomMessageBox import CustomMessageBox1
from src.ui.CustomMessageBox import CustomMessageBox
from src.core.rbac import RoleBasedAccessControl


class ManageUsersPage(QWidget):
    """Admin page for managing users"""
    
    back_clicked = Signal()
    _online_emails_ready = Signal()  # emitted from background thread to apply on main thread
    
    def __init__(self, db_manager=None, auth_service=None, sync_service=None):
        super().__init__()
        self.db = db_manager
        self.auth_service = auth_service
        self.sync_service = sync_service
        self.users = []
        self._logged_in_emails: set = set()
        self._user_page = 1
        self._user_page_size = 15
        # Track current user as logged in
        if auth_service:
            current = auth_service.get_current_user()
            if current and current.get('email'):
                self._logged_in_emails.add(current['email'])
        
        # CRITICAL: Connect sync service signals to UI update methods
        if sync_service:
            sync_service.user_updated.connect(self._on_user_updated)
            sync_service.role_changed.connect(self._on_role_changed)
            sync_service.user_created.connect(self._on_user_created)
            sync_service.user_deleted.connect(self._on_user_deleted)
            print("[MANAGE_USERS] Connected to sync service signals")
        
        self.setup_ui()
        self.load_users()
        self._online_emails_ready.connect(self._apply_online_emails)

        # Refresh online status every 15 s via both MQTT presence and backend poll
        self._online_poll_timer = QTimer()
        self._online_poll_timer.timeout.connect(self._poll_online_users)
        self._online_poll_timer.start(15000)
        # Initial poll after 1 s so table shows correct status on first open
        QTimer.singleShot(1000, self._poll_online_users)

    def _poll_online_users(self):
        """Fetch currently online users from backend REST API and refresh status column."""
        import threading
        def _fetch():
            try:
                import urllib.request, json as _json
                from src.core.config import Config
                backend = getattr(Config, 'BACKEND_URL', 'http://localhost:5000')
                with urllib.request.urlopen(f'{backend}/api/mqtt/online-users', timeout=4) as resp:
                    data = _json.loads(resp.read())
                online_emails = set(data.get('online_emails', []))
                # Merge with MQTT-tracked emails (desktop presence)
                self._pending_online_emails = online_emails | self._logged_in_emails
            except Exception:
                self._pending_online_emails = set(self._logged_in_emails)
            # Emit signal to apply on main thread (safe cross-thread)
            self._online_emails_ready.emit()
        threading.Thread(target=_fetch, daemon=True).start()

    @Slot()
    def _apply_online_emails(self):
        """Apply fetched online emails on the main thread."""
        if hasattr(self, '_pending_online_emails'):
            self._logged_in_emails = self._pending_online_emails
        self._refresh_online_from_db()

    def set_user_online(self, email: str, online: bool):
        """Called by the MQTT heartbeat handler to mark a user online/offline."""
        if online:
            self._logged_in_emails.add(email)
        else:
            self._logged_in_emails.discard(email)
        self._refresh_online_from_db()
    
    def _on_user_created(self, user: dict):
        print(f"[MANAGE_USERS] User created: {user.get('email')}")
        self.load_users_data()
        self._update_info_label()
        self._rebuild_rows()

    def _on_user_updated(self, user: dict):
        print(f"[MANAGE_USERS] User updated: {user.get('email')}")
        # Update in-memory list first
        for i, u in enumerate(self.users):
            if u['id'] == user.get('id') or u['email'] == user.get('email'):
                self.users[i].update({
                    'name': user.get('name', u['name']),
                    'role': user.get('role', u['role']),
                    'is_active': user.get('is_active', u['is_active']),
                })
                self._update_row_cells(i)
                self._update_info_label()
                return
        # Not found — full reload
        self.load_users_data()
        self._update_info_label()
        self._rebuild_rows()

    def _on_user_deleted(self, user_id: int, email: str):
        print(f"[MANAGE_USERS] User deleted: {email}")
        self.users = [u for u in self.users if u['id'] != user_id and u['email'] != email]
        self._update_info_label()
        self._rebuild_rows()

    def _on_role_changed(self, user_id: int, email: str, old_role: str, new_role: str):
        print(f"[MANAGE_USERS] Role changed for {email}: {old_role} -> {new_role}")
        for i, u in enumerate(self.users):
            if u['id'] == user_id or u['email'] == email:
                self.users[i]['role'] = new_role
                self._update_row_cells(i)
                self._update_info_label()
                return
        self.load_users_data()
        self._rebuild_rows()
    
    def setup_ui(self):
        """Setup manage users UI"""
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
        content_layout.setContentsMargins(40, 40, 40, 40)
        content_layout.setSpacing(30)
        
        # Title section
        title_layout = QHBoxLayout()
        
        title_section = QVBoxLayout()
        title_label = QLabel("Manage Users")
        title_label.setStyleSheet("font-size: 36px; font-weight: 700; color: white;")
        
        subtitle_label = QLabel("Add, edit, or remove user accounts")
        subtitle_label.setStyleSheet("font-size: 16px; color: #94a3b8;")
        
        title_section.addWidget(title_label)
        title_section.addWidget(subtitle_label)
        
        title_layout.addLayout(title_section)
        title_layout.addStretch()
        
        # Add User button
        add_btn = QPushButton("+ Add User")
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
        add_btn.clicked.connect(self.add_user)
        title_layout.addWidget(add_btn)
        
        content_layout.addLayout(title_layout)
        
        # Info box (like parameters page)
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
        self.info_label = QLabel("Total users: 0. Manage user accounts and permissions.")
        self.info_label.setStyleSheet("color: #93c5fd; font-size: 14px;")
        info_layout.addWidget(self.info_label)
        content_layout.addWidget(info_frame)
        
        # Users table
        self.create_table(content_layout)
        
        layout.addWidget(content_widget)
    
    def create_header(self, layout):
        """Create header section"""
        header_frame = QFrame()
        header_frame.setFixedHeight(90)
        header_frame.setStyleSheet("QFrame { background-color: #2d3748; border: none; }")
        
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(30, 0, 30, 0)
        
        # Logo and title
        logo_title_layout = QHBoxLayout()
        logo_title_layout.setSpacing(15)
        
        logo = QLabel()
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'logo.svg')
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo.setStyleSheet("background-color: transparent;")
            
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(50, 50)
        
        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)
        
        title_label = QLabel("PrecisionPulse")
        title_label.setStyleSheet("QLabel { color: white; font-size: 22px; font-weight: 700; background: transparent; }")
        
        subtitle_label = QLabel("User Management")
        subtitle_label.setStyleSheet("QLabel { color: #94a3b8; font-size: 14px; background: transparent; }")
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        
        logo_title_layout.addWidget(logo)
        logo_title_layout.addLayout(title_layout)
        
        header_layout.addLayout(logo_title_layout)
        header_layout.addStretch()
        
        
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
        """Create users table"""
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Name", "Email", "Role", "Status", "Actions"])
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
            }
        """)
        
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        
        table.setColumnWidth(2, 120)
        table.setColumnWidth(3, 120)
        table.setColumnWidth(4, 220)
        
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        
        self.table = table
        layout.addWidget(table)

        # Pagination controls
        pg_layout = QHBoxLayout()
        pg_layout.addStretch()

        self._user_prev_btn = QPushButton("← Prev")
        self._user_prev_btn.setStyleSheet("""
            QPushButton { background-color: #334155; color: white; border: none;
                border-radius: 6px; padding: 6px 14px; font-weight: 600; font-size: 13px; }
            QPushButton:hover { background-color: #475569; }
            QPushButton:disabled { background-color: #1e293b; color: #475569; }
        """)
        self._user_prev_btn.clicked.connect(self._prev_user_page)

        self._user_page_label = QLabel("Page 1 / 1")
        self._user_page_label.setStyleSheet("color: #94a3b8; font-size: 13px; background: transparent;")
        self._user_page_label.setAlignment(Qt.AlignCenter)

        self._user_next_btn = QPushButton("Next →")
        self._user_next_btn.setStyleSheet("""
            QPushButton { background-color: #334155; color: white; border: none;
                border-radius: 6px; padding: 6px 14px; font-weight: 600; font-size: 13px; }
            QPushButton:hover { background-color: #475569; }
            QPushButton:disabled { background-color: #1e293b; color: #475569; }
        """)
        self._user_next_btn.clicked.connect(self._next_user_page)

        pg_layout.addWidget(self._user_prev_btn)
        pg_layout.addWidget(self._user_page_label)
        pg_layout.addWidget(self._user_next_btn)
        pg_layout.addStretch()
        layout.addLayout(pg_layout)
    
    def _refresh_online_from_db(self):
        """Refresh online status column in-place."""
        self._update_info_label()
        import math
        start = (self._user_page - 1) * self._user_page_size
        page_users = self.users[start: start + self._user_page_size]
        for i, user in enumerate(page_users):
            sw = self.table.cellWidget(i, 3)
            if sw:
                lbl = sw.findChild(QLabel)
                if lbl:
                    is_active = bool(user.get('is_active', 1))
                    is_online = user['email'] in self._logged_in_emails
                    if is_online:
                        lbl.setText("\u25cf Active")
                        lbl.setStyleSheet("color: #059669; font-weight: 600; font-size: 12px;")
                    else:
                        lbl.setText("\u25cf Offline")
                        lbl.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 12px;")

    def _update_info_label(self):
        if not hasattr(self, 'info_label'):
            return
        total = len(self.users)
        online = sum(1 for u in self.users if u['email'] in self._logged_in_emails and u.get('is_active', 1))
        inactive = sum(1 for u in self.users if not u.get('is_active', 1))
        admins = sum(1 for u in self.users if u['role'] == 'admin')
        self.info_label.setText(
            f"Total: {total} | Admins: {admins} | Online: {online} | Inactive: {inactive} | Manage user accounts and permissions."
        )

    def _rebuild_rows(self):
        """Rebuild all table rows (used when row count changes)."""
        import math
        total = len(self.users)
        total_pages = max(1, math.ceil(total / self._user_page_size))
        self._user_page = max(1, min(self._user_page, total_pages))
        start = (self._user_page - 1) * self._user_page_size
        page_users = self.users[start: start + self._user_page_size]
        self.table.setRowCount(len(page_users))
        for i, user in enumerate(page_users):
            self._fill_row(i, user, start + i)
        if hasattr(self, '_user_page_label'):
            self._user_page_label.setText(f"Page {self._user_page} / {total_pages}  ({total} users)")
            self._user_prev_btn.setEnabled(self._user_page > 1)
            self._user_next_btn.setEnabled(self._user_page < total_pages)

    def _update_row_cells(self, data_index: int):
        """Update a single row in-place without rebuilding widgets."""
        import math
        start = (self._user_page - 1) * self._user_page_size
        row = data_index - start
        if row < 0 or row >= self.table.rowCount():
            return
        user = self.users[data_index]
        # Name
        item = self.table.item(row, 0)
        if item:
            item.setText(user['name'])
        # Role badge
        sw = self.table.cellWidget(row, 2)
        if sw:
            lbl = sw.findChild(QLabel)
            if lbl:
                role_color = RoleBasedAccessControl.get_role_color(user['role'])
                lbl.setText(user['role'].upper())
                lbl.setStyleSheet(
                    f"QLabel {{ background-color: {role_color}; color: white; "
                    "padding: 4px 12px; border-radius: 6px; font-weight: 600; font-size: 11px; }}"
                )
        # Online status
        sw = self.table.cellWidget(row, 3)
        if sw:
            lbl = sw.findChild(QLabel)
            if lbl:
                is_active = bool(user.get('is_active', 1))
                is_online = user['email'] in self._logged_in_emails
                if not is_active:
                    lbl.setText("\u25cf Inactive")
                    lbl.setStyleSheet("color: #6b7280; font-weight: 600; font-size: 12px;")
                elif is_online:
                    lbl.setText("\u25cf Active")
                    lbl.setStyleSheet("color: #059669; font-weight: 600; font-size: 12px;")
                else:
                    lbl.setText("\u25cf Offline")
                    lbl.setStyleSheet("color: #94a3b8; font-weight: 600; font-size: 12px;")

    def load_users_data(self):
        if not self.db:
            return
        import sqlite3
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, email, name, role, is_active FROM users ORDER BY id')
            self.users = [
                {'id': row[0], 'email': row[1], 'name': row[2], 'role': row[3], 'is_active': row[4]}
                for row in cursor.fetchall()
            ]

    def load_users(self):
        self.load_users_data()
        self._update_info_label()
        self._rebuild_rows()

    def refresh_table(self):
        """Alias kept for compatibility — delegates to zero-refresh helpers."""
        self.load_users_data()
        self._update_info_label()
        self._rebuild_rows()

    def _fill_row(self, row: int, user: dict, data_index: int):
        """Populate all cells for a single table row."""
        name_item = QTableWidgetItem(user['name'])
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 0, name_item)

        email_item = QTableWidgetItem(user['email'])
        email_item.setFlags(email_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 1, email_item)

        role_widget = QWidget()
        role_widget.setStyleSheet("background: transparent;")
        rl = QHBoxLayout(role_widget)
        rl.setContentsMargins(16, 0, 0, 0)
        role_color = RoleBasedAccessControl.get_role_color(user['role'])
        role_label = QLabel(user['role'].upper())
        role_label.setStyleSheet(
            f"QLabel {{ background-color: {role_color}; color: white; "
            "padding: 4px 12px; border-radius: 6px; font-weight: 600; font-size: 11px; }}"
        )
        rl.addWidget(role_label)
        rl.addStretch()
        self.table.setCellWidget(row, 2, role_widget)

        status_widget = QWidget()
        status_widget.setStyleSheet("background: transparent;")
        sl = QHBoxLayout(status_widget)
        sl.setContentsMargins(16, 0, 0, 0)
        is_online = user['email'] in self._logged_in_emails
        is_active = bool(user.get('is_active', 1))
        if not is_active:
            status_text = "\u25cf Inactive"
            status_color = "#6b7280"
        elif is_online:
            status_text = "\u25cf Active"
            status_color = "#059669"
        else:
            status_text = "\u25cf Offline"
            status_color = "#94a3b8"
        status_label = QLabel(status_text)
        status_label.setStyleSheet(
            f"color: {status_color}; font-weight: 600; font-size: 12px;"
        )
        sl.addWidget(status_label)
        sl.addStretch()
        self.table.setCellWidget(row, 3, status_widget)

        actions_widget = QWidget()
        actions_widget.setStyleSheet("background: transparent;")
        al = QHBoxLayout(actions_widget)
        al.setContentsMargins(0, 0, 16, 0)
        al.setSpacing(8)

        edit_btn = QPushButton("Edit Role")
        edit_btn.setFixedWidth(90)
        edit_btn.setStyleSheet("""
            QPushButton { background-color: #2563eb; color: white; border: none;
                border-radius: 6px; padding: 6px 12px; font-weight: 600; font-size: 12px; }
            QPushButton:hover { background-color: #1d4ed8; }
            QPushButton:disabled { background-color: #6b7280; color: #9ca3af; }
        """)
        edit_btn.clicked.connect(lambda checked, idx=data_index: self.edit_user(idx))

        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet("""
            QPushButton { background-color: #dc2626; color: white; border: none;
                border-radius: 6px; padding: 6px 16px; font-weight: 600; font-size: 12px; }
            QPushButton:hover { background-color: #b91c1c; }
            QPushButton:disabled { background-color: #6b7280; color: #9ca3af; }
        """)
        delete_btn.clicked.connect(lambda checked, idx=data_index: self.delete_user(idx))

        if user['email'] == 'admin@precisionpulse.com':
            edit_btn.setEnabled(False)
            delete_btn.setEnabled(False)
        elif user['role'] == 'client':
            delete_btn.setEnabled(False)

        al.addWidget(edit_btn)
        al.addWidget(delete_btn)
        al.addStretch()
        self.table.setCellWidget(row, 4, actions_widget)
        self.table.setRowHeight(row, 70)
    
    def _prev_user_page(self):
        if self._user_page > 1:
            self._user_page -= 1
            self.refresh_table()

    def _next_user_page(self):
        import math
        total_pages = max(1, math.ceil(len(self.users) / self._user_page_size))
        if self._user_page < total_pages:
            self._user_page += 1
            self.refresh_table()

    def add_user(self):
        """Show add user dialog"""
        dialog = AddUserDialog(self)
        if dialog.exec():
            user_data = dialog.get_user_data()
            if self.db:
                import sqlite3
                try:
                    with sqlite3.connect(self.db.db_path) as conn:
                        cursor = conn.cursor()
                        password_hash = self.db.ph.hash(user_data['password'])
                        cursor.execute('''
                            INSERT INTO users (email, name, password_hash, role, is_active)
                            VALUES (?, ?, ?, ?, 1)
                        ''', (user_data['email'], user_data['name'], password_hash, user_data['role']))
                        conn.commit()

                    # Publish to MQTT — backend subscriber writes to PostgreSQL
                    if self.sync_service:
                        import bcrypt
                        bcrypt_hash = bcrypt.hashpw(
                            user_data['password'].encode('utf-8'), bcrypt.gensalt()
                        ).decode('utf-8')
                        self.sync_service.publish_user_change('create', {
                            'email': user_data['email'],
                            'name': user_data['name'],
                            'password_hash': bcrypt_hash,
                            'role': user_data['role'],
                            'is_active': True
                        })

                    msg = CustomMessageBox("Success", "User added successfully!")
                    msg.exec()
                    self.refresh_table()
                except sqlite3.IntegrityError:
                    msg = CustomMessageBox("Warning", "Email already exists")
                    msg.exec()
    
    def edit_user(self, index):
        """Edit user"""
        user = self.users[index]
        dialog = EditUserDialog(self, user)
        if dialog.exec():
            user_data = dialog.get_user_data()
            if self.db:
                import sqlite3
                with sqlite3.connect(self.db.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE users SET role = ? WHERE id = ?',
                                   (user_data['role'], user['id']))
                    conn.commit()

                # Publish role change via MQTT — backend subscriber updates PostgreSQL
                if self.sync_service:
                    self.sync_service.publish_user_change('update', {
                        'email': user['email'],
                        'name': user['name'],
                        'role': user_data['role'],
                        'is_active': user_data['is_active']
                    })

                msg = CustomMessageBox("Success", "User updated successfully")
                msg.exec()
                self.refresh_table()
    
    def delete_user(self, index):
        """Delete user"""
        user = self.users[index]
        
        if user['role'] == 'client':
            msg = CustomMessageBox("Cannot Delete", "Client user cannot be deleted as it's required for telemetry data.")
            msg.exec()
            return
        
        # reply = QMessageBox.question(
        #     self, "Delete User",
        #     f"Are you sure you want to delete user '{user['name']}'?",
        #     QMessageBox.Yes | QMessageBox.No
        # )
        msg = CustomMessageBox1("Confirm Action", "Do you want to delete this user")
        result = msg.exec()  # Waits for user input

        if result == QDialog.Accepted:
           if self.db:
                import sqlite3
                with sqlite3.connect(self.db.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM users WHERE id = ?', (user['id'],))
                    conn.commit()

                # Publish deletion via MQTT — backend subscriber removes from PostgreSQL
                if self.sync_service:
                    self.sync_service.publish_user_change('delete', {
                        'email': user['email'],
                        'name': user['name'],
                        'role': user['role']
                    })

                msg = CustomMessageBox("Success", "User deleted successfully")
                msg.exec()
                self.refresh_table()
        else:
            print("User clicked No")
        
        # if reply == QMessageBox.Yes:
        #     if self.db:
        #         import sqlite3
        #         with sqlite3.connect(self.db.db_path) as conn:
        #             cursor = conn.cursor()
        #             cursor.execute('DELETE FROM users WHERE id = ?', (user['id'],))
        #             conn.commit()
                
        #         # Publish to MQTT for sync
        #         if self.sync_service:
        #             self.sync_service.publish_user_change('delete', {
        #                 'email': user['email'],
        #                 'name': user['name'],
        #                 'role': user['role']
        #             })
                
        #         QMessageBox.information(self, "Success", "User deleted successfully!")
        #         self.load_users()


class AddUserDialog(QDialog):
    """Dialog for adding new user"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup dialog UI"""
        self.setWindowTitle("")
        self.setModal(True)
        self.setFixedSize(600, 650)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Main container
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
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Title
        title = QLabel("Add New User")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: white; margin-bottom: 10px;")
        layout.addWidget(title)
        
        subtitle = QLabel("Create a new user account with role and permissions")
        subtitle.setStyleSheet("font-size: 14px; color: #94a3b8; margin-bottom: 10px;")
        layout.addWidget(subtitle)
        
        # Name
        name_label = QLabel("Full Name")
        name_label.setStyleSheet("color: #e5e7eb; font-size: 14px; font-weight: 600; margin-top: 5px;")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter full name")
        self.name_input.setFixedHeight(50)
        self.name_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 0 16px;
                color: white;
                font-size: 15px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        
        # Email
        email_label = QLabel("Email Address")
        email_label.setStyleSheet("color: #e5e7eb; font-size: 14px; font-weight: 600; margin-top: 5px;")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("user@example.com")
        self.email_input.setFixedHeight(50)
        self.email_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 0 16px;
                color: white;
                font-size: 15px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.name_input.returnPressed.connect(self.email_input.setFocus)
        
        
        
        # Password
        password_label = QLabel("Password")
        password_label.setStyleSheet("color: #e5e7eb; font-size: 14px; font-weight: 600; margin-top: 5px;")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setFixedHeight(50)
        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 0 16px;
                color: white;
                font-size: 15px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.email_input.returnPressed.connect(self.password_input.setFocus)
        
        
        # Role
        role_label = QLabel("User Role")
        role_label.setStyleSheet("color: #e5e7eb; font-size: 14px; font-weight: 600; margin-top: 5px;")
        self.role_combo = QComboBox()
        self.role_combo.addItems(["user", "admin"])
        self.role_combo.setFixedHeight(50)
        self.role_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 0 16px;
                color: white;
                font-size: 15px;
            }
            QComboBox:focus {
                border-color: #3b82f6;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: white;
                selection-background-color: #3b82f6;
            }
        """)
        self.password_input.returnPressed.connect(self.role_combo.setFocus)
        
        layout.addWidget(name_label)
        layout.addWidget(self.name_input)
        layout.addWidget(email_label)
        layout.addWidget(self.email_input)
        layout.addWidget(password_label)
        layout.addWidget(self.password_input)
        layout.addWidget(role_label)
        layout.addWidget(self.role_combo)
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        add_btn = QPushButton("Add User")
        add_btn.setFixedHeight(50)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 15px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        add_btn.clicked.connect(self.validate_and_accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(50)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #4b5563;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 15px;
            }
            QPushButton:hover { background-color: #374151; }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(add_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        main_layout.addWidget(container)
    
    def validate_and_accept(self):
        """Validate all fields before accepting"""
        if not self.name_input.text().strip():
            msg = CustomMessageBox("Validation Error", "Full Name is required!")
            msg.exec()
            return
        
        if not self.email_input.text().strip():
            msg = CustomMessageBox("Validation Error", "Email Address is required!")
            msg.exec()
            return
        
        if '@' not in self.email_input.text():
            msg = CustomMessageBox("Validation Error", "Please enter a valid email address!")
            msg.exec()
            return
        
        if not self.password_input.text():
            msg = CustomMessageBox("Validation Error", "Password is required!")
            msg.exec()
            return
        
        if len(self.password_input.text()) < 6:
            msg = CustomMessageBox("Validation Error", "Password must be at least 6 characters!")
            msg.exec()
            return
        
        self.accept()
    
    def get_user_data(self):
        """Get user data from form"""
        return {
            'name': self.name_input.text().strip(),
            'email': self.email_input.text().strip(),
            'password': self.password_input.text(),
            'role': self.role_combo.currentText()
        }


class EditUserDialog(QDialog):
    """Dialog for editing user role"""
    
    def __init__(self, parent=None, user=None):
        super().__init__(parent)
        self.user = user
        self.setup_ui()
    
    def setup_ui(self):
        """Setup dialog UI"""
        self.setWindowTitle("")
        self.setModal(True)
        self.setFixedSize(600, 500)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Main container
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
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Title
        title = QLabel("Edit User Role")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: white; margin-bottom: 10px;")
        layout.addWidget(title)
        
        subtitle = QLabel("Update the role for this user account")
        subtitle.setStyleSheet("font-size: 14px; color: #94a3b8; margin-bottom: 10px;")
        layout.addWidget(subtitle)
        
        # Name (read-only)
        name_label = QLabel("Full Name")
        name_label.setStyleSheet("color: #e5e7eb; font-size: 14px; font-weight: 600; margin-top: 5px;")
        self.name_input = QLineEdit(self.user['name'])
        self.name_input.setReadOnly(True)
        self.name_input.setFixedHeight(50)
        self.name_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 0 16px;
                color: #9ca3af;
                font-size: 15px;
            }
        """)
        
        # Email (read-only)
        email_label = QLabel("Email Address")
        email_label.setStyleSheet("color: #e5e7eb; font-size: 14px; font-weight: 600; margin-top: 5px;")
        self.email_input = QLineEdit(self.user['email'])
        self.email_input.setReadOnly(True)
        self.email_input.setFixedHeight(50)
        self.email_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 0 16px;
                color: #9ca3af;
                font-size: 15px;
            }
        """)
        
        # Role
        role_label = QLabel("User Role")
        role_label.setStyleSheet("color: #e5e7eb; font-size: 14px; font-weight: 600; margin-top: 5px;")
        self.role_combo = QComboBox()
        self.role_combo.addItems(["user", "admin"])
        self.role_combo.setCurrentText(self.user['role'])
        self.role_combo.setFixedHeight(50)
        self.role_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 0 16px;
                color: white;
                font-size: 15px;
            }
            QComboBox:focus {
                border-color: #3b82f6;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: white;
                selection-background-color: #3b82f6;
            }
        """)
        
        layout.addWidget(name_label)
        layout.addWidget(self.name_input)
        layout.addWidget(email_label)
        layout.addWidget(self.email_input)
        layout.addWidget(role_label)
        layout.addWidget(self.role_combo)
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        save_btn = QPushButton("Save Changes")
        save_btn.setFixedHeight(50)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 15px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(50)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #4b5563;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 15px;
            }
            QPushButton:hover { background-color: #374151; }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        main_layout.addWidget(container)
    
    def get_user_data(self):
        """Get user data from form"""
        return {
            'name': self.user['name'],
            'role': self.role_combo.currentText(),
            'is_active': self.user['is_active']
        }
