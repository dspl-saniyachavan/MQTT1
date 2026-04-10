'use client';

import dynamic from 'next/dynamic';

const ProfileContent = dynamic(() => import('./content'), {
  loading: () => (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500 mx-auto mb-3" />
        <p className="text-slate-400 text-sm">Loading Profile…</p>
      </div>
    </div>
  ),
  ssr: false,
});

export default function ProfilePage() {
  return <ProfileContent />;
}
