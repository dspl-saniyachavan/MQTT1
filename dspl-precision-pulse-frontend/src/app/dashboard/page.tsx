'use client';

import dynamic from 'next/dynamic';
import ProtectedPage from '@/components/ProtectedPage';

const DashboardContent = dynamic(() => import('./content'), {
  loading: () => <PageLoader label="Dashboard" />,
  ssr: false,
});

function PageLoader({ label }: { label: string }) {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500 mx-auto mb-3" />
        <p className="text-slate-400 text-sm">Loading {label}…</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedPage requiredPermission="view_dashboard">
      <DashboardContent />
    </ProtectedPage>
  );
}
