'use client';

import MqttStatusIndicator from './MqttStatusIndicator';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

export default function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div style={{
      background: 'linear-gradient(90deg, #4892e1 0%, #5ba0ef 50%, #6dadf0 100%)',
      padding: '14px 28px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      boxShadow: '0 2px 12px rgba(72,146,225,0.2)',
      flexShrink: 0,
      gap: 16,
    }}>
      <div>
        <h1 style={{
          color: '#ffffff',
          fontWeight: 700,
          fontSize: 18,
          margin: 0,
          lineHeight: 1.3,
        }}>
          {title}
        </h1>
        {subtitle && (
          <p style={{
            color: 'rgba(255,255,255,0.75)',
            fontSize: 12,
            margin: '2px 0 0',
          }}>
            {subtitle}
          </p>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {actions}
        <MqttStatusIndicator showLabel size="sm" />
      </div>
    </div>
  );
}
