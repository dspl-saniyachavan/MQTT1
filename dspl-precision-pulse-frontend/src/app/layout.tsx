import type { Metadata } from 'next';
import './globals.css';
import ErrorHandlerInit from '@/components/ErrorHandlerInit';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'PrecisionPulse - Real-time Telemetry Platform',
  description: 'Hybrid web-and-desktop ecosystem for real-time telemetry streaming',
  icons: { icon: '/favicon.svg' },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body suppressHydrationWarning style={{ margin: 0, padding: 0, height: '100%', overflow: 'hidden' }}>
        <ErrorHandlerInit />
        <AppShell>{children}</AppShell>
        <script dangerouslySetInnerHTML={{ __html: `if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(()=>{})}` }} />
      </body>
    </html>
  );
}
