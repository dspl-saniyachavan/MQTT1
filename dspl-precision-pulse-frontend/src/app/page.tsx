'use client';

export default function Home() {
  // Server-side redirect handled by middleware
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="text-white text-xl animate-pulse">Loading...</div>
    </div>
  );
}
