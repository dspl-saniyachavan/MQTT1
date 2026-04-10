'use client';

/**
 * Set a cookie with the authentication token
 */
export function setTokenCookie(token: string, days: number = 7): void {
  if (typeof document === 'undefined') return;
  
  const expires = new Date();
  expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `token=${token}; expires=${expires.toUTCString()}; path=/; SameSite=Lax${secure}`;
}

/**
 * Get a cookie value by name
 */
export function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  
  const nameEQ = name + '=';
  const ca = document.cookie.split(';');
  
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) === ' ') c = c.substring(1, c.length);
    if (c.startsWith(nameEQ)) return c.substring(nameEQ.length, c.length);
  }
  
  return null;
}

/**
 * Get the authentication token from cookie
 */
export function getTokenCookie(): string | null {
  return getCookie('token');
}

/**
 * Delete a cookie by name
 */
export function deleteCookie(name: string): void {
  if (typeof document === 'undefined') return;
  
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
}

/**
 * Delete the authentication token cookie
 */
export function deleteTokenCookie(): void {
  deleteCookie('token');
}

/**
 * Check if user is authenticated (has valid token)
 */
export function isAuthenticated(): boolean {
  const token = getTokenCookie();
  return token !== null && token.length > 0;
}
