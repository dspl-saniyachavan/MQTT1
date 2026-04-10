'use client';

import { useEffect, useState } from 'react';
import { Role, Permission, hasPermission } from '@/lib/rbac';

interface RBACGuardProps {
  children: React.ReactNode;
  permission: Permission;
  fallback?: React.ReactNode;
}

export default function RBACGuard({ children, permission, fallback = null }: RBACGuardProps) {
  const [hasAccess, setHasAccess] = useState(false);

  useEffect(() => {
    const userData = localStorage.getItem('user');
    if (userData) {
      const user = JSON.parse(userData);
      setHasAccess(hasPermission(user.role as Role, permission));
    }
  }, [permission]);

  return hasAccess ? <>{children}</> : <>{fallback}</>;
}
