"""
Role-based access control for UI elements
"""

from typing import Dict, List, Optional


class RoleBasedAccessControl:
    """Manage role-based UI access and visibility"""
    
    # Permission matrix: role -> feature -> action -> allowed
    PERMISSIONS = {
        'admin': {
            'users': {'create': True, 'read': True, 'update': True, 'delete': True},
            'parameters': {'create': True, 'read': True, 'update': True, 'delete': True},
            'telemetry': {'read': True, 'stream': True},
            'roles': {'manage': True},
            'permissions': {'manage': True}
        },
        'user': {
            'users': {'create': False, 'read': False, 'update': False, 'delete': False},
            'parameters': {'create': False, 'read': True, 'update': False, 'delete': False},
            'telemetry': {'read': True, 'stream': True},
            'roles': {'manage': False},
            'permissions': {'manage': False}
        },
        'client': {
            'users': {'create': False, 'read': False, 'update': False, 'delete': False},
            'parameters': {'create': False, 'read': True, 'update': False, 'delete': False},
            'telemetry': {'read': True, 'stream': True},
            'roles': {'manage': False},
            'permissions': {'manage': False}
        }
    }
    
    # UI visibility: role -> feature -> visible
    VISIBILITY = {
        'admin': {
            'manage_users_button': True,
            'manage_users_page': True,
            'parameters_button': True,
            'parameters_page': True,
            'profile_button': True,
            'telemetry_widget': True,
            'add_parameter_button': True,
            'edit_parameter_button': True,
            'delete_parameter_button': True,
            'edit_values_button': True,
            'configuration_button': True,
        },
        'user': {
            'manage_users_button': False,
            'manage_users_page': False,
            'parameters_button': False,
            'parameters_page': False,
            'profile_button': True,
            'telemetry_widget': True,
            'add_parameter_button': False,
            'edit_parameter_button': False,
            'delete_parameter_button': False,
            'edit_values_button': False,
            'configuration_button': False,
        },
        'client': {
            'manage_users_button': False,
            'manage_users_page': False,
            'parameters_button': True,
            'parameters_page': True,
            'profile_button': True,
            'telemetry_widget': True,
            'add_parameter_button': False,
            'edit_parameter_button': False,
            'delete_parameter_button': False,
            'edit_values_button': False,
            'configuration_button': False,
        }
    }
    
    @staticmethod
    def can_access(role: str, feature: str, action: str) -> bool:
        """Check if role can perform action on feature"""
        if role not in RoleBasedAccessControl.PERMISSIONS:
            return False
        
        feature_perms = RoleBasedAccessControl.PERMISSIONS[role].get(feature, {})
        return feature_perms.get(action, False)
    
    @staticmethod
    def is_visible(role: str, ui_element: str) -> bool:
        """Check if UI element should be visible for role"""
        if role not in RoleBasedAccessControl.VISIBILITY:
            return False
        
        return RoleBasedAccessControl.VISIBILITY[role].get(ui_element, False)
    
    @staticmethod
    def get_allowed_actions(role: str, feature: str) -> List[str]:
        """Get all allowed actions for role on feature"""
        if role not in RoleBasedAccessControl.PERMISSIONS:
            return []
        
        feature_perms = RoleBasedAccessControl.PERMISSIONS[role].get(feature, {})
        return [action for action, allowed in feature_perms.items() if allowed]
    
    @staticmethod
    def get_visible_elements(role: str) -> List[str]:
        """Get all visible UI elements for role"""
        if role not in RoleBasedAccessControl.VISIBILITY:
            return []
        
        visibility = RoleBasedAccessControl.VISIBILITY[role]
        return [element for element, visible in visibility.items() if visible]
    
    @staticmethod
    def apply_role_restrictions(widget, role: str, element_name: str):
        """Apply role-based restrictions to a widget"""
        if not RoleBasedAccessControl.is_visible(role, element_name):
            widget.hide()
            widget.setEnabled(False)
        else:
            widget.show()
            widget.setEnabled(True)
    
    @staticmethod
    def get_role_display_name(role: str) -> str:
        """Get display name for role"""
        role_names = {
            'admin': 'Administrator',
            'user': 'User',
            'client': 'Client'
        }
        return role_names.get(role, role.capitalize())
    
    @staticmethod
    def get_role_color(role: str) -> str:
        """Get color for role badge"""
        role_colors = {
            'admin': '#7c3aed',
            'user': '#059669',
            'client': '#2563eb'
        }
        return role_colors.get(role, '#6b7280')
    
    @staticmethod
    def get_role_description(role: str) -> str:
        """Get description for role"""
        descriptions = {
            'admin': 'Full access to all features and user management',
            'user': 'Read-only access to parameters and telemetry',
            'client': 'Access to parameters and telemetry streaming'
        }
        return descriptions.get(role, 'Unknown role')
