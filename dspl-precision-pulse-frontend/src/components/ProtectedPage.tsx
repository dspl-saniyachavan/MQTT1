'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Role, Permission, hasPermission } from '@/lib/rbac';

interface ProtectedPageProps {
  children: React.ReactNode;
  requiredPermission: Permission;
  fallback?: React.ReactNode;
}

export default function ProtectedPage({ 
  children, 
  requiredPermission, 
  fallback 
}: ProtectedPageProps) {
  const [hasAccess, setHasAccess] = useState(false);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const userData = localStorage.getItem('user');
    const token = localStorage.getItem('token');

    if (!token || !userData) {
      router.push('/login');
      return;
    }

    try {
      const user = JSON.parse(userData);
      const access = hasPermission(user.role as Role, requiredPermission);
      
      if (!access) {
        setHasAccess(false);
        setLoading(false);
        return;
      }

      setHasAccess(true);
    } catch (error) {
      router.push('/login');
    } finally {
      setLoading(false);
    }
  }, [requiredPermission, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!hasAccess) {
    return (
      fallback || (
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <h1 className="text-3xl font-bold text-red-600 mb-4">Access Denied</h1>
            <p className="text-gray-600 mb-6">You don't have permission to access this page.</p>
            <button
              onClick={() => window.location.href = '/dashboard'}
              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      )
    );
  }

  return <>{children}</>;
}
