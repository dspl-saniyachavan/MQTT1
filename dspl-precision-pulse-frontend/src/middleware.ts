import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server'
import { verifyToken } from '@/lib/jwt';

const adminRoutes = ['/users', '/parameters', '/edit-values', '/config', '/commands'];
const protectedRoutes = ['/dashboard', '/profile', '/users', '/parameters', '/config', '/history', '/edit-values', '/commands', '/alert-events'];

function sanitizeLog(input: string): string {
  return input.replace(/[\n\r]/g, ' ').slice(0, 200);
}

function isProtected(pathname: string): boolean {
  return protectedRoutes.some(route => pathname.startsWith(route));
}

function isAdmin(pathname: string): boolean {
  return adminRoutes.some(route => pathname.startsWith(route));
}

async function handleLogin(request: NextRequest, token: string | undefined) {
  if (!token) return NextResponse.next();
  const payload = await verifyToken(token);
  if (payload) return NextResponse.redirect(new URL('/dashboard', request.url));
  return NextResponse.next();
}

async function handleRoot(request: NextRequest, token: string | undefined) {
  if (!token) return NextResponse.redirect(new URL('/login', request.url));
  const payload = await verifyToken(token);
  if (!payload) return NextResponse.redirect(new URL('/login', request.url));
  return NextResponse.redirect(new URL('/dashboard', request.url));
}

async function handleProtected(request: NextRequest, token: string | undefined, pathname: string) {
  if (!token) return NextResponse.redirect(new URL('/login', request.url));
  const payload = await verifyToken(token);
  if (!payload) return NextResponse.redirect(new URL('/login', request.url));
  if (isAdmin(pathname) && payload.role !== 'admin') {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }
  return NextResponse.next();
}

export async function middleware(request: NextRequest) {
  const token = request.cookies.get('token')?.value;
  const { pathname } = request.nextUrl;

  if (pathname === '/login') return handleLogin(request, token);
  if (pathname === '/') return handleRoot(request, token);
  if (isProtected(pathname)) return handleProtected(request, token, pathname);

  return NextResponse.next();
}

export const config = {
  matcher: ['/', '/dashboard/:path*', '/profile/:path*', '/users/:path*', '/parameters/:path*', '/config/:path*', '/history/:path*', '/edit-values/:path*', '/commands/:path*', '/alert-events/:path*', '/login'],
};
