'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

export default function ProfileContent() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [user, setUser] = useState<any>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [profileForm, setProfileForm] = useState({ name: '', email: '' });
  const [profileError, setProfileError] = useState('');
  const [profileSuccess, setProfileSuccess] = useState('');
  const [profileLoading, setProfileLoading] = useState(false);

  const [pwForm, setPwForm] = useState({ currentPassword: '', newPassword: '', confirmPassword: '' });
  const [pwError, setPwError] = useState('');
  const [pwSuccess, setPwSuccess] = useState('');
  const [pwLoading, setPwLoading] = useState(false);

  // Fetch fresh user data from backend on mount
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) { router.push('/login'); return; }

    const storedUser = localStorage.getItem('user');
    if (!storedUser) { router.push('/login'); return; }
    const parsed = JSON.parse(storedUser);

    fetch(`${BACKEND}/api/users/${parsed.id}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
      .then(res => res.ok ? res.json() : Promise.reject(res.status))
      .then(data => {
        setUser(data);
        setProfileForm({ name: data.name || '', email: data.email || '' });
        if (data.avatar_url) setAvatarUrl(data.avatar_url);
        localStorage.setItem('user', JSON.stringify({ ...parsed, name: data.name, email: data.email, role: data.role }));
      })
      .catch(() => {
        setUser(parsed);
        setProfileForm({ name: parsed.name || '', email: parsed.email || '' });
      });
  }, [router]);

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      const dataUrl = reader.result as string;
      setAvatarUrl(dataUrl);
      try {
        const { mqttUsers } = await import('@/services/mqttBridgeService');
        await mqttUsers.update({ id: user.id, email: user.email, avatar_url: dataUrl });
      } catch { /* silent — avatar already shown in UI */ }
    };
    reader.readAsDataURL(file);
  };

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileError('');
    setProfileSuccess('');
    setProfileLoading(true);

    if (!profileForm.name.trim()) { setProfileError('Name is required'); setProfileLoading(false); return; }

    try {
      const { mqttUsers } = await import('@/services/mqttBridgeService');
      const result = await mqttUsers.update({ id: user.id, email: user.email, name: profileForm.name });
      if (result.ok) {
        setUser((prev: any) => ({ ...prev, name: profileForm.name }));
        const stored = localStorage.getItem('user');
        if (stored) {
          const parsed = JSON.parse(stored);
          localStorage.setItem('user', JSON.stringify({ ...parsed, name: profileForm.name }));
        }
        setProfileSuccess('Profile updated successfully');
      } else {
        setProfileError(result.error || 'Failed to update profile');
      }
    } catch {
      setProfileError('Network error');
    } finally {
      setProfileLoading(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwError('');
    setPwSuccess('');
    setPwLoading(true);

    if (!pwForm.currentPassword) { setPwError('Current password is required'); setPwLoading(false); return; }
    if (pwForm.newPassword !== pwForm.confirmPassword) { setPwError('New passwords do not match'); setPwLoading(false); return; }
    if (pwForm.newPassword.length < 6) { setPwError('Password must be at least 6 characters'); setPwLoading(false); return; }
    if (!/[a-z]/.test(pwForm.newPassword)) { setPwError('Password must contain at least one lowercase letter'); setPwLoading(false); return; }
    if (!/[0-9]/.test(pwForm.newPassword)) { setPwError('Password must contain at least one number'); setPwLoading(false); return; }

    try {
      // Password change requires current-password verification — use HTTP (auth-gated)
      const token = localStorage.getItem('token');
      const res = await fetch(`${BACKEND}/api/users/${user.id}/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ currentPassword: pwForm.currentPassword, newPassword: pwForm.newPassword }),
      });
      if (res.ok) {
        setPwSuccess('Password changed successfully');
        setPwForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
      } else {
        const data = await res.json();
        setPwError(data.error || 'Failed to change password');
      }
    } catch {
      setPwError('Network error');
    } finally {
      setPwLoading(false);
    }
  };

  if (!user) return null;

  const initials = user.name?.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2) || 'U';

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 border-b border-indigo-500/20 sticky top-0 z-50">
        <div className="px-8 py-4">
          <h1 className="text-2xl font-bold text-white">Profile</h1>
          <p className="text-sm text-slate-400">Manage your account</p>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-8 py-10 space-y-6">

        {/* Avatar Card */}
        <div className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-8 flex items-center gap-6">
          <div className="relative group">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="w-24 h-24 rounded-full cursor-pointer overflow-hidden ring-4 ring-indigo-500/40 hover:ring-indigo-500/80 transition-all duration-200"
            >
              {avatarUrl ? (
                <img src={avatarUrl} alt="avatar" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full bg-gradient-to-br from-indigo-600 to-indigo-400 flex items-center justify-center">
                  <span className="text-white font-bold text-2xl">{initials}</span>
                </div>
              )}
              <div className="absolute inset-0 bg-black/50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                  <circle cx="12" cy="13" r="4" />
                </svg>
              </div>
            </div>
            <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleAvatarChange} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">{user.name}</h2>
            <p className="text-slate-400 text-sm mt-0.5">{user.email}</p>
            <span className={`inline-block mt-2 px-3 py-1 rounded-full text-xs font-semibold ${
              user.role === 'admin' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' :
              user.role === 'client' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' :
              'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
            }`}>
              {user.role?.toUpperCase()}
            </span>
            <p className="text-xs text-slate-500 mt-2">Click avatar to change photo</p>
            {avatarUrl && (
              <button
                onClick={async () => {
                  setAvatarUrl(null);
                  try {
                    const { mqttUsers } = await import('@/services/mqttBridgeService');
                    await mqttUsers.update({ id: user.id, email: user.email, avatar_url: null });
                  } catch { /* silent */ }
                }}
                className="mt-2 text-xs text-red-400 hover:text-red-300 underline transition-colors"
              >
                Remove photo
              </button>
            )}
          </div>
        </div>

        {/* Edit Profile */}
        <div className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-8">
          <h2 className="text-lg font-bold text-white mb-6">Edit Profile</h2>
          <form onSubmit={handleProfileUpdate} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1.5">Full Name</label>
              <input
                type="text"
                value={profileForm.name}
                onChange={e => setProfileForm({ ...profileForm, name: e.target.value })}
                className="w-full px-4 py-3 bg-slate-900/60 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-colors"
                placeholder="Your full name"
                disabled={profileLoading}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1.5">Email Address</label>
              <input
                type="email"
                value={profileForm.email}
                readOnly
                disabled
                className="w-full px-4 py-3 bg-slate-900/60 border border-slate-600 rounded-lg text-slate-500 cursor-not-allowed opacity-70 focus:outline-none"
              />
              <p className="mt-1 text-xs text-slate-600">Email cannot be changed</p>
            </div>

            {profileError && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">{profileError}</div>
            )}
            {profileSuccess && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 text-sm">{profileSuccess}</div>
            )}

            <button
              type="submit"
              disabled={profileLoading}
              className="w-full py-3 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-700 hover:to-indigo-600 disabled:opacity-50 text-white font-semibold rounded-lg transition-all"
            >
              {profileLoading ? 'Saving...' : 'Save Changes'}
            </button>
          </form>
        </div>

        {/* Change Password */}
        <div className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-8">
          <h2 className="text-lg font-bold text-white mb-6">Change Password</h2>
          <form onSubmit={handlePasswordChange} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1.5">Current Password</label>
              <input
                type="password"
                value={pwForm.currentPassword}
                onChange={e => setPwForm({ ...pwForm, currentPassword: e.target.value })}
                className="w-full px-4 py-3 bg-slate-900/60 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-colors"
                disabled={pwLoading}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1.5">New Password</label>
              <input
                type="password"
                value={pwForm.newPassword}
                onChange={e => setPwForm({ ...pwForm, newPassword: e.target.value })}
                className="w-full px-4 py-3 bg-slate-900/60 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-colors"
                disabled={pwLoading}
              />
              <p className="mt-1.5 text-xs text-slate-500">Min 6 chars, one lowercase letter, one number</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1.5">Confirm New Password</label>
              <input
                type="password"
                value={pwForm.confirmPassword}
                onChange={e => setPwForm({ ...pwForm, confirmPassword: e.target.value })}
                className="w-full px-4 py-3 bg-slate-900/60 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition-colors"
                disabled={pwLoading}
              />
            </div>

            {pwError && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">{pwError}</div>
            )}
            {pwSuccess && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 text-sm">{pwSuccess}</div>
            )}

            <button
              type="submit"
              disabled={pwLoading}
              className="w-full py-3 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-700 hover:to-indigo-600 disabled:opacity-50 text-white font-semibold rounded-lg transition-all"
            >
              {pwLoading ? 'Updating...' : 'Update Password'}
            </button>
          </form>
        </div>

      </div>
    </div>
  );
}
