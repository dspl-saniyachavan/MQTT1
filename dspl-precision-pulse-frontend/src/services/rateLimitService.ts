/**
 * Frontend Rate Limiting Service
 * Handles rate limit responses from backend and implements client-side throttling
 */

interface RateLimitConfig {
  maxRequests: number;
  windowMs: number;
  retryAfter?: number;
}

interface RequestQueue {
  timestamp: number;
  count: number;
}

class RateLimitService {
  private requestQueues: Map<string, RequestQueue[]> = new Map();
  private rateLimitConfigs: Map<string, RateLimitConfig> = new Map();
  private retryTimeouts: Map<string, NodeJS.Timeout> = new Map();

  constructor() {
    this.initializeDefaultConfigs();
  }

  private initializeDefaultConfigs(): void {
    // Authentication endpoints - stricter
    this.rateLimitConfigs.set('/api/auth/login', {
      maxRequests: 5,
      windowMs: 60000, // 1 minute
    });

    this.rateLimitConfigs.set('/api/auth/register', {
      maxRequests: 3,
      windowMs: 60000,
    });

    // User management - moderate
    this.rateLimitConfigs.set('/api/users', {
      maxRequests: 30,
      windowMs: 60000,
    });

    // Telemetry - high volume
    this.rateLimitConfigs.set('/api/telemetry', {
      maxRequests: 100,
      windowMs: 60000,
    });

    // Parameters - moderate
    this.rateLimitConfigs.set('/api/parameters', {
      maxRequests: 50,
      windowMs: 60000,
    });

    // Configuration - moderate
    this.rateLimitConfigs.set('/api/config', {
      maxRequests: 30,
      windowMs: 60000,
    });

    // Default for other endpoints
    this.rateLimitConfigs.set('default', {
      maxRequests: 100,
      windowMs: 60000,
    });
  }

  /**
   * Check if request is allowed based on rate limits
   */
  canMakeRequest(endpoint: string): boolean {
    const config = this.rateLimitConfigs.get(endpoint) || this.rateLimitConfigs.get('default')!;
    const queue = this.requestQueues.get(endpoint) || [];

    const now = Date.now();
    const windowStart = now - config.windowMs;

    // Remove old requests outside the window
    const validRequests = queue.filter((req) => req.timestamp > windowStart);

    // Check if we can make a request
    if (validRequests.length < config.maxRequests) {
      validRequests.push({ timestamp: now, count: 1 });
      this.requestQueues.set(endpoint, validRequests);
      return true;
    }

    return false;
  }

  /**
   * Get remaining requests for an endpoint
   */
  getRemainingRequests(endpoint: string): number {
    const config = this.rateLimitConfigs.get(endpoint) || this.rateLimitConfigs.get('default')!;
    const queue = this.requestQueues.get(endpoint) || [];

    const now = Date.now();
    const windowStart = now - config.windowMs;

    const validRequests = queue.filter((req) => req.timestamp > windowStart);
    return Math.max(0, config.maxRequests - validRequests.length);
  }

  /**
   * Get time until next request is allowed
   */
  getRetryAfter(endpoint: string): number {
    const config = this.rateLimitConfigs.get(endpoint) || this.rateLimitConfigs.get('default')!;
    const queue = this.requestQueues.get(endpoint) || [];

    if (queue.length === 0) return 0;

    const oldestRequest = queue[0];
    const retryTime = oldestRequest.timestamp + config.windowMs;
    const now = Date.now();

    return Math.max(0, retryTime - now);
  }

  /**
   * Handle rate limit response from server
   */
  handleRateLimitResponse(endpoint: string, retryAfter?: number): void {
    const delay = retryAfter || this.getRetryAfter(endpoint);

    // Clear existing timeout if any
    const existingTimeout = this.retryTimeouts.get(endpoint);
    if (existingTimeout) {
      clearTimeout(existingTimeout);
    }

    // Set new timeout
    const timeout = setTimeout(() => {
      this.requestQueues.delete(endpoint);
      this.retryTimeouts.delete(endpoint);
    }, delay);

    this.retryTimeouts.set(endpoint, timeout);
  }

  /**
   * Reset rate limit for an endpoint
   */
  resetEndpoint(endpoint: string): void {
    this.requestQueues.delete(endpoint);
    const timeout = this.retryTimeouts.get(endpoint);
    if (timeout) {
      clearTimeout(timeout);
      this.retryTimeouts.delete(endpoint);
    }
  }

  /**
   * Reset all rate limits
   */
  resetAll(): void {
    this.requestQueues.clear();
    this.retryTimeouts.forEach((timeout) => clearTimeout(timeout));
    this.retryTimeouts.clear();
  }

  /**
   * Get rate limit status for all endpoints
   */
  getStatus(): Record<string, any> {
    const status: Record<string, any> = {};

    this.rateLimitConfigs.forEach((config, endpoint) => {
      if (endpoint !== 'default') {
        status[endpoint] = {
          remaining: this.getRemainingRequests(endpoint),
          retryAfter: this.getRetryAfter(endpoint),
          config,
        };
      }
    });

    return status;
  }
}

// Export singleton instance
export const rateLimitService = new RateLimitService();

/**
 * Wrapper for fetch with rate limiting
 */
export async function fetchWithRateLimit(
  endpoint: string,
  options?: RequestInit
): Promise<Response> {
  if (!rateLimitService.canMakeRequest(endpoint)) {
    const retryAfter = rateLimitService.getRetryAfter(endpoint);
    const error = new Error(`Rate limit exceeded. Retry after ${retryAfter}ms`);
    (error as any).retryAfter = retryAfter;
    (error as any).statusCode = 429;
    throw error;
  }

  try {
    const response = await fetch(endpoint, options);

    // Handle rate limit response from server
    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After');
      rateLimitService.handleRateLimitResponse(
        endpoint,
        retryAfter ? parseInt(retryAfter) * 1000 : undefined
      );

      const error = new Error('Rate limit exceeded');
      (error as any).statusCode = 429;
      (error as any).retryAfter = rateLimitService.getRetryAfter(endpoint);
      throw error;
    }

    return response;
  } catch (error) {
    throw error;
  }
}
