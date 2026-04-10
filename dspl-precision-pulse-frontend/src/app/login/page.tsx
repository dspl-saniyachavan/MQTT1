'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { setTokenCookie } from '@/lib/cookieManager';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';
      const res = await fetch(`${backendUrl}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || 'Login failed. Please try again.');
        return;
      }

      localStorage.setItem('token', data.token);
      localStorage.setItem('user', JSON.stringify(data.user));
      setTokenCookie(data.token);

      // Connect Socket.IO so real-time events work across all pages
      try {
        const { socketIOService } = await import('@/services/socketIOService');
        await socketIOService.connect(data.token);
      } catch (_) {}

      router.push('/dashboard');
    } catch (err: any) {
      setError('Network error. Please check your connection and try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="w-full max-w-md">
        <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-3xl shadow-2xl p-10 border border-slate-700">
          {/* Logo */}
          <div className="text-center mb-10">
            <img src="/logo.svg" alt="PrecisionPulse Logo" className="w-20 h-20 mx-auto mb-5" />
            <h1 className="text-4xl font-extrabold text-white mb-3 tracking-tight">Welcome Back</h1>
            <p className="text-slate-400 text-base">Sign in to PrecisionPulse</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-semibold text-slate-300 mb-2">Email Address</label>
              <input
                type="email"
                placeholder="admin@precisionpulse.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-3 border-2 border-slate-600 rounded-lg  focus:outline-none text-white bg-slate-700/50 placeholder-slate-500"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-300 mb-2">Password</label>
              <input
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-3 border-2 border-slate-600 rounded-lg  focus:outline-none text-white bg-slate-700/50 placeholder-slate-500"
              />
            </div>

            {error && (
              <div className="p-4 bg-red-500/20 border-l-4 border-red-500 rounded-lg">
                <p className="font-semibold text-red-400">✖ Authentication Failed</p>
                <p className="text-sm text-red-300 mt-1">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 disabled:from-slate-600 disabled:to-slate-700 text-white rounded-lg font-semibold text-lg transition-all"
            >
              {isLoading ? 'Signing In...' : 'Sign In'}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-8">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-700"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-gradient-to-br from-slate-800 to-slate-900 text-slate-400 font-medium">
                New to PrecisionPulse?
              </span>
            </div>
          </div>

          {/* Register Link */}
          <div className="text-center">
            <p className="text-slate-400 text-sm">
              Contact your administrator to create an account
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
