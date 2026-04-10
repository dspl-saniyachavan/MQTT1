'use client';

import { useRouter, usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import RBACGuard from './RBACGuard';
import { Permission } from '@/lib/rbac';

interface NavItem {
  label: string;
  href: string;
  icon: string;   // SVG path data
  permission?: Permission;
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard',      href: '/dashboard',      icon: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>' },
  { label: 'Parameters',     href: '/parameters',     icon: '<circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>', permission: 'manage_parameters' },
  { label: 'Users',          href: '/users',          icon: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>', permission: 'manage_users' },
  { label: 'History',        href: '/history',        icon: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>' },
  { label: 'Config',         href: '/config',         icon: '<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>', permission: 'manage_config' },
  { label: 'Config History', href: '/config-history', icon: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>', permission: 'manage_config' },
  { label: 'Edit Values',    href: '/edit-values',    icon: '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>', permission: 'manage_parameters' },
  { label: 'Audit Logs',     href: '/audit-logs',     icon: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>', permission: 'manage_users' },
  { label: 'Conflicts',      href: '/conflicts',      icon: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>', permission: 'manage_users' },
  { label: 'Alert Events',   href: '/alert-events',   icon: '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>' },
  { label: 'Reports',        href: '/reports',        icon: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>' },
  { label: 'Profile',        href: '/profile',        icon: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>' },
];

function NavIcon({ d }: { d: string }) {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      dangerouslySetInnerHTML={{ __html: d }}
    />
  );
}

export default function Sidebar() {
  const router   = useRouter();
  const pathname = usePathname();

  // Start empty so SSR and first client render match — no active highlight on server
  const [activePath, setActivePath] = useState('');
  useEffect(() => { setActivePath(pathname ?? ''); }, [pathname]);

  const isActive = (href: string) =>
    activePath === href || activePath.startsWith(href + '/');

  const renderItem = (item: NavItem) => {
    const active = isActive(item.href);

    const el = (
      <div
        key={item.label}
        title={item.label}
        onClick={() => router.push(item.href)}
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '9px 12px', borderRadius: 8, cursor: 'pointer',
          marginBottom: 1,
          background: active ? 'linear-gradient(90deg,#4f46e5,#6366f1)' : 'transparent',
          color: active ? '#fff' : '#94a3b8',
          fontSize: 13, fontWeight: active ? 600 : 400,
          boxShadow: active ? '0 2px 8px rgba(99,102,241,.3)' : 'none',
          transition: 'all .15s',
          userSelect: 'none',
        }}
        onMouseEnter={e => {
          if (!active) {
            const el = e.currentTarget as HTMLDivElement;
            el.style.background = 'rgba(51,65,85,.6)';
            el.style.color = '#e2e8f0';
          }
        }}
        onMouseLeave={e => {
          if (!active) {
            const el = e.currentTarget as HTMLDivElement;
            el.style.background = 'transparent';
            el.style.color = '#94a3b8';
          }
        }}
      >
        <span style={{ flexShrink: 0, display: 'flex', opacity: active ? 1 : 0.75 }}>
          <NavIcon d={item.icon} />
        </span>
        <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {item.label}
        </span>
        {active && (
          <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'rgba(255,255,255,.8)', flexShrink: 0 }} />
        )}
      </div>
    );

    return item.permission
      ? <RBACGuard key={item.label} permission={item.permission}>{el}</RBACGuard>
      : <div key={item.label}>{el}</div>;
  };

  return (
    <div style={{
      width: '100%', height: '100%',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Logo */}
      <div style={{ padding: '18px 14px 14px', borderBottom: '1px solid #1e293b', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 8, flexShrink: 0,
            background: 'linear-gradient(135deg,#4f46e5,#818cf8)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          </div>
          <div>
            <div style={{ color: '#f1f5f9', fontWeight: 700, fontSize: 14, lineHeight: 1.2 }}>PrecisionPulse</div>
            <div style={{ color: '#475569', fontSize: 11 }}>Telemetry</div>
          </div>
        </div>
      </div>

      {/* Nav items */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '10px 8px' }}>
        {NAV_ITEMS.map(renderItem)}
      </nav>

      {/* Logout */}
      <div style={{ padding: '8px 8px 12px', borderTop: '1px solid #1e293b', flexShrink: 0 }}>
        <button
          onClick={() => {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            document.cookie = 'token=; path=/; max-age=0';
            router.push('/login');
          }}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: 10,
            padding: '9px 12px', borderRadius: 8, border: 'none', cursor: 'pointer',
            background: 'linear-gradient(90deg,#dc2626,#ef4444)',
            color: '#fff', fontWeight: 600, fontSize: 13,
          }}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          Logout
        </button>
      </div>
    </div>
  );
}
