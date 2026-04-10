export type Role = 'admin' | 'user';
export type Permission = 
  | 'view_dashboard'
  | 'manage_users'
  | 'view_profile'
  | 'manage_parameters'
  | 'view_telemetry'
  | 'view_audit_logs'
  | 'view_history'
  | 'view_reports'
  | 'manage_config'
  | 'view_parameters'
  | 'edit_parameters'
  | 'view_remote_commands'
  | 'execute_remote_commands'
  | 'view_buffer'
  | 'manage_buffer';

const rolePermissions: Record<Role, Permission[]> = {
  admin: [
    'view_dashboard',
    'manage_users',
    'view_profile',
    'manage_parameters',
    'view_telemetry',
    'view_audit_logs',
    'view_history',
    'view_reports',
    'manage_config',
    'view_parameters',
    'edit_parameters',
    'view_remote_commands',
    'execute_remote_commands',
    'view_buffer',
    'manage_buffer',
  ],
  user: [
    'view_dashboard',
    'view_profile',
    'view_telemetry',
    'view_history',
    'view_parameters',
  ],
};

export function hasPermission(role: Role, permission: Permission): boolean {
  return rolePermissions[role]?.includes(permission) || false;
}

export function getAllPermissions(): Permission[] {
  return [
    'view_dashboard',
    'manage_users',
    'view_profile',
    'manage_parameters',
    'view_telemetry',
    'view_audit_logs',
    'view_history',
    'view_reports',
    'manage_config',
    'view_parameters',
    'edit_parameters',
    'view_remote_commands',
    'execute_remote_commands',
    'view_buffer',
    'manage_buffer',
  ];
}

export function hasRole(userRole: string, allowedRoles: Role[]): boolean {
  return allowedRoles.includes(userRole as Role);
}
