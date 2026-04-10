"""
Unit tests for role-based access control
"""

import unittest
from src.core.rbac import RoleBasedAccessControl


class TestRoleBasedAccessControl(unittest.TestCase):
    """Test role-based access control"""
    
    def test_admin_can_access_all_features(self):
        """Test admin has access to all features"""
        self.assertTrue(RoleBasedAccessControl.can_access('admin', 'users', 'create'))
        self.assertTrue(RoleBasedAccessControl.can_access('admin', 'users', 'read'))
        self.assertTrue(RoleBasedAccessControl.can_access('admin', 'users', 'update'))
        self.assertTrue(RoleBasedAccessControl.can_access('admin', 'users', 'delete'))
        self.assertTrue(RoleBasedAccessControl.can_access('admin', 'parameters', 'create'))
        self.assertTrue(RoleBasedAccessControl.can_access('admin', 'roles', 'manage'))
    
    def test_user_read_only_access(self):
        """Test user has read-only access"""
        self.assertFalse(RoleBasedAccessControl.can_access('user', 'users', 'create'))
        self.assertFalse(RoleBasedAccessControl.can_access('user', 'users', 'read'))
        self.assertFalse(RoleBasedAccessControl.can_access('user', 'parameters', 'create'))
        self.assertTrue(RoleBasedAccessControl.can_access('user', 'parameters', 'read'))
        self.assertTrue(RoleBasedAccessControl.can_access('user', 'telemetry', 'read'))
    
    def test_client_access(self):
        """Test client access permissions"""
        self.assertFalse(RoleBasedAccessControl.can_access('client', 'users', 'create'))
        self.assertFalse(RoleBasedAccessControl.can_access('client', 'parameters', 'create'))
        self.assertTrue(RoleBasedAccessControl.can_access('client', 'parameters', 'read'))
        self.assertTrue(RoleBasedAccessControl.can_access('client', 'telemetry', 'stream'))
    
    def test_admin_ui_visibility(self):
        """Test admin sees all UI elements"""
        self.assertTrue(RoleBasedAccessControl.is_visible('admin', 'manage_users_button'))
        self.assertTrue(RoleBasedAccessControl.is_visible('admin', 'manage_users_page'))
        self.assertTrue(RoleBasedAccessControl.is_visible('admin', 'parameters_button'))
        self.assertTrue(RoleBasedAccessControl.is_visible('admin', 'add_parameter_button'))
    
    def test_user_ui_visibility(self):
        """Test user UI visibility restrictions"""
        self.assertFalse(RoleBasedAccessControl.is_visible('user', 'manage_users_button'))
        self.assertFalse(RoleBasedAccessControl.is_visible('user', 'manage_users_page'))
        self.assertFalse(RoleBasedAccessControl.is_visible('user', 'parameters_button'))
        self.assertTrue(RoleBasedAccessControl.is_visible('user', 'profile_button'))
        self.assertTrue(RoleBasedAccessControl.is_visible('user', 'telemetry_widget'))
    
    def test_client_ui_visibility(self):
        """Test client UI visibility"""
        self.assertFalse(RoleBasedAccessControl.is_visible('client', 'manage_users_button'))
        self.assertTrue(RoleBasedAccessControl.is_visible('client', 'parameters_button'))
        self.assertTrue(RoleBasedAccessControl.is_visible('client', 'parameters_page'))
        self.assertTrue(RoleBasedAccessControl.is_visible('client', 'telemetry_widget'))
    
    def test_get_allowed_actions(self):
        """Test getting allowed actions for role"""
        admin_actions = RoleBasedAccessControl.get_allowed_actions('admin', 'users')
        self.assertIn('create', admin_actions)
        self.assertIn('read', admin_actions)
        self.assertIn('update', admin_actions)
        self.assertIn('delete', admin_actions)
        
        user_actions = RoleBasedAccessControl.get_allowed_actions('user', 'parameters')
        self.assertIn('read', user_actions)
        self.assertNotIn('create', user_actions)
        self.assertNotIn('update', user_actions)
    
    def test_get_visible_elements(self):
        """Test getting visible elements for role"""
        admin_elements = RoleBasedAccessControl.get_visible_elements('admin')
        self.assertIn('manage_users_button', admin_elements)
        self.assertIn('parameters_button', admin_elements)
        
        user_elements = RoleBasedAccessControl.get_visible_elements('user')
        self.assertNotIn('manage_users_button', user_elements)
        self.assertNotIn('parameters_button', user_elements)
        self.assertIn('profile_button', user_elements)
    
    def test_role_display_names(self):
        """Test role display names"""
        self.assertEqual(RoleBasedAccessControl.get_role_display_name('admin'), 'Administrator')
        self.assertEqual(RoleBasedAccessControl.get_role_display_name('user'), 'User')
        self.assertEqual(RoleBasedAccessControl.get_role_display_name('client'), 'Client')
    
    def test_role_colors(self):
        """Test role colors"""
        self.assertEqual(RoleBasedAccessControl.get_role_color('admin'), '#7c3aed')
        self.assertEqual(RoleBasedAccessControl.get_role_color('user'), '#059669')
        self.assertEqual(RoleBasedAccessControl.get_role_color('client'), '#2563eb')
    
    def test_role_descriptions(self):
        """Test role descriptions"""
        admin_desc = RoleBasedAccessControl.get_role_description('admin')
        self.assertIn('Full access', admin_desc)
        
        user_desc = RoleBasedAccessControl.get_role_description('user')
        self.assertIn('Read-only', user_desc)
        
        client_desc = RoleBasedAccessControl.get_role_description('client')
        self.assertIn('telemetry', client_desc)
    
    def test_invalid_role(self):
        """Test invalid role handling"""
        self.assertFalse(RoleBasedAccessControl.can_access('invalid', 'users', 'read'))
        self.assertFalse(RoleBasedAccessControl.is_visible('invalid', 'profile_button'))
        self.assertEqual(RoleBasedAccessControl.get_allowed_actions('invalid', 'users'), [])
        self.assertEqual(RoleBasedAccessControl.get_visible_elements('invalid'), [])
    
    def test_permission_hierarchy(self):
        """Test permission hierarchy across roles"""
        # Admin has most permissions
        admin_perms = len(RoleBasedAccessControl.get_allowed_actions('admin', 'users'))
        user_perms = len(RoleBasedAccessControl.get_allowed_actions('user', 'users'))
        client_perms = len(RoleBasedAccessControl.get_allowed_actions('client', 'users'))
        
        self.assertGreater(admin_perms, user_perms)
        self.assertGreater(admin_perms, client_perms)
        self.assertEqual(user_perms, 0)
        self.assertEqual(client_perms, 0)
    
    def test_ui_visibility_hierarchy(self):
        """Test UI visibility hierarchy across roles"""
        admin_elements = RoleBasedAccessControl.get_visible_elements('admin')
        user_elements = RoleBasedAccessControl.get_visible_elements('user')
        client_elements = RoleBasedAccessControl.get_visible_elements('client')
        
        # Admin should see most elements
        self.assertGreater(len(admin_elements), len(user_elements))
        self.assertGreater(len(admin_elements), len(client_elements))


if __name__ == '__main__':
    unittest.main()
