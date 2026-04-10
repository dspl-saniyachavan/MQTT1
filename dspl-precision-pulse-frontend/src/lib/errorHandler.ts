/**
 * Error Handler Utility for Frontend
 * Catches and logs all console errors with context
 * Safe for Next.js SSR
 */

interface ErrorLog {
  timestamp: string;
  type: string;
  message: string;
  stack?: string;
  context?: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
}

class ErrorHandler {
  private errors: ErrorLog[] = [];
  private maxErrors = 100;
  private isClient = false;

  constructor() {
    // Only setup on client side
    if (typeof window !== 'undefined') {
      this.isClient = true;
      this.setupGlobalErrorHandlers();
    }
  }

  private setupGlobalErrorHandlers() {
    if (!this.isClient) return;

    // Handle uncaught errors
    window.addEventListener('error', (event: ErrorEvent) => {
      this.logError({
        type: 'UncaughtError',
        message: event.message,
        stack: event.error?.stack,
        severity: 'error',
        context: `${event.filename}:${event.lineno}:${event.colno}`
      });
    });

    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
      this.logError({
        type: 'UnhandledPromiseRejection',
        message: event.reason?.message || String(event.reason),
        stack: event.reason?.stack,
        severity: 'error'
      });
    });

    // Intercept console.error
    const originalError = console.error;
    console.error = (...args: any[]) => {
      originalError.apply(console, args);
      const message = args.map(arg =>
        typeof arg === 'object' ? JSON.stringify(arg) : String(arg)
      ).join(' ');
      // Ignore transient Socket.IO transport errors — expected during reconnection
      if (message.includes('xhr poll error') || message.includes('websocket error') || message.includes('transport error')) return;
      this.logError({ type: 'ConsoleError', message, severity: 'error' });
    };

    // Intercept console.warn
    const originalWarn = console.warn;
    console.warn = (...args: any[]) => {
      originalWarn.apply(console, args);
      this.logError({
        type: 'ConsoleWarn',
        message: args.map(arg => 
          typeof arg === 'object' ? JSON.stringify(arg) : String(arg)
        ).join(' '),
        severity: 'warning'
      });
    };
  }

  private logError(error: Omit<ErrorLog, 'timestamp'>) {
    if (!this.isClient) return;

    const errorLog: ErrorLog = {
      timestamp: new Date().toISOString(),
      ...error
    };

    this.errors.push(errorLog);

    // Keep only last N errors
    if (this.errors.length > this.maxErrors) {
      this.errors.shift();
    }

    // Log to console with styling
    this.printError(errorLog);

    // Send to backend if critical
    if (error.severity === 'critical' || error.severity === 'error') {
      this.sendToBackend(errorLog);
    }
  }

  private printError(error: ErrorLog) {
    if (!this.isClient) return;

    const colors = {
      info: 'color: #0ea5e9',
      warning: 'color: #f59e0b',
      error: 'color: #ef4444',
      critical: 'color: #dc2626; font-weight: bold'
    };

    console.log(
      `%c[${error.type}] ${error.message}`,
      colors[error.severity],
      error
    );
  }

  private async sendToBackend(error: ErrorLog) {
    if (!this.isClient) return;

    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
      const backendUrl = typeof window !== 'undefined' ? (process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000') : 'http://localhost:5000';
      await fetch(`${backendUrl}/api/errors`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          type: error.type,
          message: error.message,
          stack: error.stack,
          context: error.context,
          severity: error.severity,
          timestamp: error.timestamp,
          url: typeof window !== 'undefined' ? window.location.href : 'unknown',
          userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown'
        })
      });
    } catch (err) {
      // Silently fail - don't create infinite loop
    }
  }

  public getErrors(): ErrorLog[] {
    return [...this.errors];
  }

  public getErrorsByType(type: string): ErrorLog[] {
    return this.errors.filter(e => e.type === type);
  }

  public getErrorsBySeverity(severity: string): ErrorLog[] {
    return this.errors.filter(e => e.severity === severity);
  }

  public clearErrors() {
    this.errors = [];
  }

  public printSummary() {
    if (!this.isClient) {
      console.log('Error handler not available on server side');
      return;
    }

    console.group('📊 Error Summary');
    console.log(`Total Errors: ${this.errors.length}`);
    
    const bySeverity = {
      info: this.errors.filter(e => e.severity === 'info').length,
      warning: this.errors.filter(e => e.severity === 'warning').length,
      error: this.errors.filter(e => e.severity === 'error').length,
      critical: this.errors.filter(e => e.severity === 'critical').length
    };
    
    console.table(bySeverity);
    
    const byType: { [key: string]: number } = {};
    this.errors.forEach(e => {
      byType[e.type] = (byType[e.type] || 0) + 1;
    });
    
    console.log('By Type:');
    console.table(byType);
    
    console.groupEnd();
  }

  public exportErrors(): string {
    return JSON.stringify(this.errors, null, 2);
  }
}

// Initialize error handler only on client side
const errorHandler = typeof window !== 'undefined' ? new ErrorHandler() : null;

// Make available globally for debugging
if (typeof window !== 'undefined' && errorHandler) {
  (window as any).errorHandler = errorHandler;
}

// Export for use in components
export default errorHandler || { 
  getErrors: () => [], 
  printSummary: () => console.log('Error handler not available'),
  getErrorsByType: () => [],
  getErrorsBySeverity: () => [],
  clearErrors: () => {},
  exportErrors: () => '{}'
};
