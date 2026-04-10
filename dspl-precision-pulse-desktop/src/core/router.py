"""
Router for managing navigation and route guards
"""

from PySide6.QtCore import QObject, Signal
from typing import Dict, Optional, Callable

class Route:
    """Route definition"""
    def __init__(self, name: str, widget_factory: Callable, requires_auth: bool = True, allowed_roles: list = None):
        self.name = name
        self.widget_factory = widget_factory
        self.requires_auth = requires_auth
        self.allowed_roles = allowed_roles or []

class Router(QObject):
    """Application router with authentication guards"""
    
    route_changed = Signal(str)
    unauthorized_access = Signal()
    
    def __init__(self):
        super().__init__()
        self.routes: Dict[str, Route] = {}
        self.current_route: Optional[str] = None
        self.current_user: Optional[Dict] = None
        self.history = []
    
    def register_route(self, name: str, widget_factory: Callable, requires_auth: bool = True, allowed_roles: list = None):
        """Register a new route"""
        self.routes[name] = Route(name, widget_factory, requires_auth, allowed_roles)
    
    def set_user(self, user: Optional[Dict]):
        """Set current authenticated user"""
        self.current_user = user
    
    def navigate(self, route_name: str, **kwargs) -> bool:
        """Navigate to a route with authentication check"""
        if route_name not in self.routes:
            return False
        
        route = self.routes[route_name]
        
        # Check authentication
        if route.requires_auth and not self.current_user:
            self.unauthorized_access.emit()
            return False
        
        # Check role authorization
        if route.allowed_roles and self.current_user:
            if self.current_user.get('role') not in route.allowed_roles:
                self.unauthorized_access.emit()
                return False
        
        # Navigate
        if self.current_route:
            self.history.append(self.current_route)
        
        self.current_route = route_name
        self.route_changed.emit(route_name)
        return True
    
    def go_back(self) -> bool:
        """Navigate to previous route"""
        if self.history:
            previous = self.history.pop()
            self.current_route = previous
            self.route_changed.emit(previous)
            return True
        return False
    
    def get_current_route(self) -> Optional[str]:
        """Get current route name"""
        return self.current_route
    
    def can_access(self, route_name: str) -> bool:
        """Check if current user can access route"""
        if route_name not in self.routes:
            return False
        
        route = self.routes[route_name]
        
        if route.requires_auth and not self.current_user:
            return False
        
        if route.allowed_roles and self.current_user:
            if self.current_user.get('role') not in route.allowed_roles:
                return False
        
        return True
    