import { NextRequest, NextResponse } from 'next/server';
import axios from 'axios';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

function isValidUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export async function POST(request: NextRequest) {
  try {
    if (!isValidUrl(BACKEND_URL)) {
      return NextResponse.json(
        { error: 'Invalid backend URL' },
        { status: 500 }
      );
    }

    const body = await request.json();
    const { email, password } = body;

    if (!email || !password) {
      return NextResponse.json(
        { error: 'Email and password required' },
        { status: 400 }
      );
    }

    const response = await axios.post(
      `${BACKEND_URL}/api/auth/login`,
      { email, password },
      { timeout: 5000 }
    );

    const token = response.data?.token;
    const res = NextResponse.json(response.data, { status: 200 });

    // Set HttpOnly cookie server-side for middleware-based auth
    if (token) {
      res.cookies.set('token', token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: 60 * 60 * 24, // 24 hours
        path: '/',
      });
    }

    return res;
  } catch (error: any) {
    const message = error.response?.data?.error || error.message || 'Authentication failed';
    return NextResponse.json(
      { error: message },
      { status: error.response?.status || 401 }
    );
  }
}
