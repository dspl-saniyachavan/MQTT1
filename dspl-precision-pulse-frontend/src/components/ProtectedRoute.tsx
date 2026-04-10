'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Role, hasRole } from '@/lib/rbac';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles: Role[];
  redirectTo?: string;
}

export default function ProtectedRoute({ children, allowedRoles, redirectTo = '/dashboard' }: ProtectedRouteProps) {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const userData = localStorage.getItem('user');

    if (!token) {
      router.push('/login');
      return;
    }

    if (userData) {
      const user = JSON.parse(userData);
      if (hasRole(user.role, allowedRoles)) {
        setAuthorized(true);
      } else {
        router.push(redirectTo);
      }
    }
  }, [router, allowedRoles, redirectTo]);

  if (!authorized) return null;

  return <>{children}</>;
}
