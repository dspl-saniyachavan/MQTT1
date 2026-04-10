self.addEventListener('push', function(event) {
  if (!event.data) return;
  let data = {};
  try { data = event.data.json(); } catch { data = { title: 'Alert', body: event.data.text() }; }

  const severity = data.severity || 'warning';
  const icon = severity === 'critical' ? '/favicon.svg' : '/favicon.svg';
  const badgeColor = severity === 'critical' ? '#ef4444' : '#f59e0b';

  event.waitUntil(
    self.registration.showNotification(data.title || 'PrecisionPulse Alert', {
      body: data.body || '',
      icon,
      badge: icon,
      tag: `alert-${severity}`,
      renotify: true,
      vibrate: severity === 'critical' ? [200, 100, 200, 100, 200] : [200, 100, 200],
      data: { url: '/alert-events' },
    })
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const url = event.notification.data?.url || '/alert-events';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
      for (const client of clientList) {
        if (client.url.includes(url) && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
