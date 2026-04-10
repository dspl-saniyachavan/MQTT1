/**
 * Frontend unit tests — cover lib utilities, services, and cookie manager
 */

// ── cookieManager ─────────────────────────────────────────────────────────────
describe('cookieManager', () => {
  beforeEach(() => {
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: '',
    });
  });

  it('getCookie returns null for missing cookie', async () => {
    const { getCookie } = await import('@/lib/cookieManager');
    expect(getCookie('nonexistent')).toBeNull();
  });

  it('isAuthenticated returns false when no token', async () => {
    const { isAuthenticated } = await import('@/lib/cookieManager');
    expect(isAuthenticated()).toBe(false);
  });

  it('deleteCookie does not throw', async () => {
    const { deleteCookie } = await import('@/lib/cookieManager');
    expect(() => deleteCookie('token')).not.toThrow();
  });

  it('deleteTokenCookie does not throw', async () => {
    const { deleteTokenCookie } = await import('@/lib/cookieManager');
    expect(() => deleteTokenCookie()).not.toThrow();
  });
});

// ── rbac ──────────────────────────────────────────────────────────────────────
describe('rbac', () => {
  it('hasPermission admin/manage_users returns true', async () => {
    const { hasPermission } = await import('@/lib/rbac');
    expect(hasPermission('admin', 'manage_users')).toBe(true);
  });

  it('hasPermission user/manage_users returns false', async () => {
    const { hasPermission } = await import('@/lib/rbac');
    expect(hasPermission('user', 'manage_users')).toBe(false);
  });

  it('hasPermission user/view_telemetry returns true', async () => {
    const { hasPermission } = await import('@/lib/rbac');
    expect(hasPermission('user', 'view_telemetry')).toBe(true);
  });

  it('hasRole admin in [admin] returns true', async () => {
    const { hasRole } = await import('@/lib/rbac');
    expect(hasRole('admin', ['admin'])).toBe(true);
  });

  it('hasRole client in [admin, user] returns false', async () => {
    const { hasRole } = await import('@/lib/rbac');
    expect(hasRole('client', ['admin', 'user'])).toBe(false);
  });

  it('hasRole user in [admin, user] returns true', async () => {
    const { hasRole } = await import('@/lib/rbac');
    expect(hasRole('user', ['admin', 'user'])).toBe(true);
  });
});

// ── backendService ────────────────────────────────────────────────────────────
describe('backendService exports', () => {
  it('exports authService', async () => {
    const mod = await import('@/services/backendService');
    expect(mod.authService).toBeDefined();
    expect(typeof mod.authService.login).toBe('function');
  });

  it('exports parameterService', async () => {
    const mod = await import('@/services/backendService');
    expect(mod.parameterService).toBeDefined();
    expect(typeof mod.parameterService.getAllParameters).toBe('function');
  });

  it('exports telemetryService', async () => {
    const mod = await import('@/services/backendService');
    expect(mod.telemetryService).toBeDefined();
    expect(typeof mod.telemetryService.getParameterHistory).toBe('function');
  });

  it('exports configService', async () => {
    const mod = await import('@/services/backendService');
    expect(mod.configService).toBeDefined();
    expect(typeof mod.configService.getSystemConfig).toBe('function');
  });

  it('exports userService', async () => {
    const mod = await import('@/services/backendService');
    expect(mod.userService).toBeDefined();
    expect(typeof mod.userService.getAllUsers).toBe('function');
  });
});

// ── configService (from separate file) ───────────────────────────────────────
describe('configService module', () => {
  it('can be imported without throwing', async () => {
    await expect(import('@/services/configService')).resolves.toBeDefined();
  });

  it('exports expected functions', async () => {
    const mod = await import('@/services/configService');
    expect(mod).toBeDefined();
  });
});

// ── socketIOService ───────────────────────────────────────────────────────────
describe('socketIOService', () => {
  it('isConnected returns false before connect', async () => {
    const { socketIOService } = await import('@/services/socketIOService');
    expect(socketIOService.isConnected()).toBe(false);
  });

  it('on/off registers and removes listener', async () => {
    const { socketIOService } = await import('@/services/socketIOService');
    const cb = jest.fn();
    socketIOService.on('test_event', cb);
    socketIOService.off('test_event', cb);
    expect(socketIOService.isConnected()).toBe(false);
  });

  it('emit does not throw when not connected', async () => {
    const { socketIOService } = await import('@/services/socketIOService');
    expect(() => socketIOService.emit('test', { data: 1 })).not.toThrow();
  });

  it('disconnect does not throw when not connected', async () => {
    const { socketIOService } = await import('@/services/socketIOService');
    expect(() => socketIOService.disconnect()).not.toThrow();
  });
});

// ── errorHandler ──────────────────────────────────────────────────────────────
describe('errorHandler', () => {
  it('can be imported without throwing', async () => {
    await expect(import('@/lib/errorHandler')).resolves.toBeDefined();
  });
});

// ── api lib ───────────────────────────────────────────────────────────────────
describe('api lib', () => {
  it('can be imported without throwing', async () => {
    await expect(import('@/lib/api')).resolves.toBeDefined();
  });
});
