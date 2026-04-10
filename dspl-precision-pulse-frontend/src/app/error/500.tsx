'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Error500() {
  const router = useRouter();

  useEffect(() => {
    console.error('500 Internal Server Error');
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <div className="mb-8">
          <h1 className="text-9xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-red-600 to-red-500 mb-4">
            500
          </h1>
          <h2 className="text-3xl font-bold text-white mb-2">Server Error</h2>
          <p className="text-slate-400 text-lg">
            Something went wrong on our end.
          </p>
        </div>

        <div className="bg-red-600/20 border border-red-500/30 rounded-lg p-6 mb-8">
          <p className="text-red-400 text-sm mb-4">
            We're experiencing technical difficulties:
          </p>
          <ul className="text-left text-red-300 text-sm space-y-2">
            <li>• Database connection error</li>
            <li>• Service temporarily unavailable</li>
            <li>• Internal server error</li>
            <li>• Please try again later</li>
          </ul>
        </div>

        <div className="flex flex-col gap-3">
          <button
            onClick={() => router.refresh()}
            className="w-full px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg transition-colors"
          >
            Retry
          </button>
          <button
            onClick={() => router.push('/dashboard')}
            className="w-full px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white font-semibold rounded-lg transition-colors"
          >
            Go to Dashboard
          </button>
          <button
            onClick={() => router.push('/login')}
            className="w-full px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white font-semibold rounded-lg transition-colors"
          >
            Go to Login
          </button>
        </div>

        <div className="mt-8 pt-8 border-t border-slate-700">
          <p className="text-slate-500 text-sm">
            Our team has been notified. Please try again in a few moments.
          </p>
          <a
            href="mailto:support@precisionpulse.com"
            className="text-indigo-400 hover:text-indigo-300 text-sm mt-2 inline-block"
          >
            Contact Support
          </a>
        </div>
      </div>
    </div>
  );
}
