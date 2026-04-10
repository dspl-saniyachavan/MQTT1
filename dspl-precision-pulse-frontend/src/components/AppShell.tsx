'use client';

import { usePathname } from 'next/navigation';
import Sidebar from './Sidebar';

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLogin  = pathname === '/login' || pathname === '/';

  if (isLogin) {
    return (
      <div style={{ width: '100%', height: '100%', overflowY: 'auto' }}>
        {children}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden' }}>
      {/* Sidebar — fixed width column, never scrolls */}
      <div style={{
        width: 256,
        minWidth: 256,
        flexShrink: 0,
        height: '100%',
        overflowY: 'auto',
        overflowX: 'hidden',
        background: 'linear-gradient(180deg,#0f172a 0%,#1e293b 50%,#0f172a 100%)',
        borderRight: '1px solid #1e293b',
      }}>
        <Sidebar />
      </div>

      {/* Content — scrolls independently */}
      <div style={{
        flex: 1,
        minWidth: 0,
        height: '100%',
        overflowY: 'auto',
        overflowX: 'hidden',
      }}>
        {children}
      </div>
    </div>
  );
}
