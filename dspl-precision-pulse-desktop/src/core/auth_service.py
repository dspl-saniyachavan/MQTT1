"""
Authentication service for managing user sessions
"""

from PySide6.QtCore import QObject, Signal
from typing import Optional, Dict
from datetime import datetime, timedelta
import secrets

class AuthService(QObject):
    """Authentication service with session management"""
    
    user_logged_in = Signal(dict)
    user_logged_out = Signal()
    session_expired = Signal()
    
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.current_user: Optional[Dict] = None
        self.session_token: Optional[str] = None
        self.session_expiry: Optional[datetime] = None
        self.session_duration = timedelta(hours=8)
    
    def login(self, email: str, password: str) -> bool:
        user = self.db_manager.authenticate_user(email, password)
        
        if user:
            self.current_user = user
            self._password = password
            self.session_token = secrets.token_urlsafe(32)
            self.session_expiry = datetime.now() + self.session_duration
            self._jwt_token = None
            self.user_logged_in.emit(user)
            return True
        
        return False
    
    def logout(self):
        """Clear user session"""
        self.current_user = None
        self.session_token = None
        self.session_expiry = None
        self.user_logged_out.emit()
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        if not self.current_user or not self.session_expiry:
            return False
        
        if datetime.now() > self.session_expiry:
            self.session_expired.emit()
            self.logout()
            return False
        
        return True
    
    def get_current_user(self) -> Optional[Dict]:
        """Get current authenticated user"""
        return self.current_user
    
    def has_role(self, role: str) -> bool:
        """Check if current user has specific role"""
        if not self.is_authenticated():
            return False
        return self.current_user.get('role') == role
    
    def has_any_role(self, roles: list) -> bool:
        """Check if current user has any of the specified roles"""
        if not self.is_authenticated():
            return False
        return self.current_user.get('role') in roles
    
    def get_token(self) -> Optional[str]:
        """Return a local session token — desktop uses MQTT, not HTTP bearer tokens."""
        return self.session_token if self.is_authenticated() else None
    
    def refresh_session(self):
        """Refresh session expiry"""
        if self.is_authenticated():
            self.session_expiry = datetime.now() + self.session_duration
