'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { socketIOService } from '@/services/socketIOService';

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  isActive: boolean;
  createdAt: string;
}

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

export default function UsersContent() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [loggedInEmails, setLoggedInEmails] = useState<Set<string>>(new Set());
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({ name: '', email: '', password: '', role: 'user' });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [userPage, setUserPage] = useState(1);
  const USER_PAGE_SIZE = 10;

  useEffect(() => {
    const userData = localStorage.getItem('user');
    if (userData) {
      const u = JSON.parse(userData);
      setCurrentUser(u);
      setLoggedInEmails(new Set([u.email]));
    }
    fetchUsers();
    fetchOnlineUsers();
    setupSocketListeners();
    return () => {
      socketIOService.off('user_created');
      socketIOService.off('user_updated');
      socketIOService.off('user_deleted');
      socketIOService.off('user_logged_in');
      socketIOService.off('user_logged_out');
    };
  }, []);

  const setupSocketListeners = () => {
    socketIOService.on('user_created', (data: any) => {
      // Backend emits { user: {...} } wrapper
      const u = data.user ?? data;
      const newUser: User = {
        id: u.id?.toString() || '',
        email: u.email || '',
        name: u.name || '',
        role: u.role || 'user',
        isActive: u.is_active !== false,
        createdAt: u.created_at || new Date().toISOString(),
      };
      setUsers(prev => prev.some(x => x.email === newUser.email) ? prev : [...prev, newUser]);
    });

    socketIOService.on('user_updated', (data: any) => {
      // Backend emits { user: {...} } wrapper
      const u = data.user ?? data;
      const uid = u.id?.toString();
      const email = u.email;
      setUsers(prev => prev.map(x =>
        (uid && x.id === uid) || (email && x.email === email)
          ? { ...x, role: u.role ?? x.role, name: u.name ?? x.name, isActive: u.is_active ?? x.isActive }
          : x
      ));
    });

    socketIOService.on('user_deleted', (data: any) => {
      const uid = (data.user_id ?? data.id)?.toString();
      const email = data.email;
      setUsers(prev => prev.filter(x => x.id !== uid && x.email !== email));
    });

    socketIOService.on('user_logged_in', (data: any) => {
      if (data?.email) setLoggedInEmails(prev => new Set([...prev, data.email]));
    });
    socketIOService.on('user_logged_out', (data: any) => {
      if (data?.email) setLoggedInEmails(prev => { const n = new Set(prev); n.delete(data.email); return n; });
    });
  };

  const fetchOnlineUsers = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${BACKEND}/api/users/online`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const data = await res.json();
        setLoggedInEmails(prev => new Set([...prev, ...(data.online_emails || [])]));
      }
    } catch { /* ignore */ }
  };

  const fetchUsers = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${BACKEND}/api/users`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const data = await res.json();
        setUsers(data.map((u: any) => ({
          id: u.id.toString(), email: u.email, name: u.name,
          role: u.role, isActive: u.is_active, createdAt: u.created_at,
        })));
      }
    } catch (err) { console.error('Failed to fetch users:', err); }
  };

  const isOnline = (email: string) => loggedInEmails.has(email);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors([]);
    const validationErrors: string[] = [];
    if (!editingId && users.some(u => u.email === formData.email)) validationErrors.push('Email already exists');
    if (!editingId && formData.password.length < 6) validationErrors.push('Password must be at least 6 characters');
    if (!editingId && !/[A-Z]/.test(formData.password)) validationErrors.push('Password must contain at least one uppercase letter');
    if (!editingId && !/[a-z]/.test(formData.password)) validationErrors.push('Password must contain at least one lowercase letter');
    if (!editingId && !/[0-9]/.test(formData.password)) validationErrors.push('Password must contain at least one number');
    if (validationErrors.length > 0) { setErrors(validationErrors); return; }

    try {
      const { mqttUsers } = await import('@/services/mqttBridgeService');
      if (editingId) {
        const user = users.find(u => u.id === editingId);
        const result = await mqttUsers.changeRole(Number(editingId), user?.email || '', user?.role || '', formData.role);
        if (result.ok) {
          setShowModal(false);
          setFormData({ name: '', email: '', password: '', role: 'user' });
          setEditingId(null); setErrors([]);
          setUsers(users.map(u => u.id === editingId ? { ...u, role: formData.role } : u));
        } else { setErrors([result.error || 'Failed to update user']); }
      } else {
        // Hash password client-side before sending over MQTT
        const result = await mqttUsers.create({
          email: formData.email, name: formData.name,
          password_hash: formData.password, // backend subscriber hashes it
          role: formData.role, is_active: true,
        });
        if (result.ok) {
          setShowModal(false);
          setFormData({ name: '', email: '', password: '', role: 'user' });
          setEditingId(null); setErrors([]);
          // Socket.IO user_created will trigger fetchUsers()
        } else { setErrors([result.error || 'Failed to create user']); }
      }
    } catch { setErrors(['Network error']); }
  };

  const handleEdit = (user: User) => {
    setFormData({ name: user.name, email: user.email, password: '', role: user.role });
    setEditingId(user.id); setShowModal(true);
  };

  const handleDelete = async (id: string) => {
    if (id === currentUser?.id) { alert('You cannot delete yourself!'); return; }
    if (!confirm('Delete this user?')) return;
    try {
      const user = users.find(u => u.id === id);
      const { mqttUsers } = await import('@/services/mqttBridgeService');
      const result = await mqttUsers.delete({ id: Number(id), email: user?.email || '' });
      if (result.ok) setUsers(users.filter(u => u.id !== id));
      else alert(result.error || 'Failed to delete user');
    } catch { alert('Error deleting user'); }
  };

  if (!currentUser) return null;

  // Stats
  const totalUsers = users.length;
  const adminCount = users.filter(u => u.role === 'admin').length;
  const activeCount = users.filter(u => u.isActive).length;
  const onlineCount = users.filter(u => isOnline(u.email)).length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 border-b border-indigo-500/20 sticky top-0 z-50">
        <div className="px-4 sm:px-8 py-4">
          <h1 className="text-lg sm:text-2xl font-bold text-white">User Management</h1>
          <p className="text-xs sm:text-sm text-slate-400">Add, edit, or remove user accounts</p>
        </div>
      </div>

      <div className="px-4 sm:px-8 lg:px-20 py-12">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
          <div>
            <h2 className="text-2xl sm:text-4xl font-bold text-white mb-2">Manage Users</h2>
            <p className="text-sm sm:text-lg text-slate-400">Add, edit, or remove user accounts</p>
          </div>
          <button
            onClick={() => { setShowModal(true); setEditingId(null); setFormData({ name: '', email: '', password: '', role: 'user' }); }}
            className="w-full sm:w-auto px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg"
          >
            + Add User
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Total Users', value: totalUsers, color: 'text-indigo-400', bg: 'bg-indigo-900/20 border-indigo-700/40' },
            { label: 'Admins', value: adminCount, color: 'text-purple-400', bg: 'bg-purple-900/20 border-purple-700/40' },
            { label: 'Active Accounts', value: activeCount, color: 'text-emerald-400', bg: 'bg-emerald-900/20 border-emerald-700/40' },
            { label: 'Currently Online', value: onlineCount, color: 'text-sky-400', bg: 'bg-sky-900/20 border-sky-700/40' },
          ].map(({ label, value, color, bg }) => (
            <div key={label} className={`rounded-xl border p-4 ${bg}`}>
              <div className={`text-3xl font-bold ${color}`}>{value}</div>
              <div className="text-slate-400 text-xs mt-1">{label}</div>
            </div>
          ))}
        </div>

        {/* Table */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden overflow-x-auto">
          <table className="w-full min-w-[600px] text-sm">
            <thead className="bg-slate-700/50 border-b border-slate-600">
              <tr>
                <th className="px-4 py-3 text-left text-slate-300 font-semibold">Name</th>
                <th className="px-4 py-3 text-left text-slate-300 font-semibold">Email</th>
                <th className="px-4 py-3 text-left text-slate-300 font-semibold">Role</th>
                <th className="px-4 py-3 text-left text-slate-300 font-semibold">Status</th>
                <th className="px-4 py-3 text-left text-slate-300 font-semibold">Created</th>
                <th className="px-4 py-3 text-right text-slate-300 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60">
              {users.slice((userPage - 1) * USER_PAGE_SIZE, userPage * USER_PAGE_SIZE).map((user) => {
                const online = isOnline(user.email);
                return (
                  <tr key={user.id} className="hover:bg-slate-700/20 transition-colors">
                    <td className="px-4 py-3 text-white font-medium">{user.name}</td>
                    <td className="px-4 py-3 text-slate-400">{user.email}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${user.role === 'admin' ? 'bg-purple-900/40 text-purple-300' : 'bg-blue-900/40 text-blue-300'}`}>
                        {user.role.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold ${online ? 'bg-emerald-900/40 text-emerald-300' : 'bg-red-900/40 text-red-400'}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${online ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
                        {online ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{new Date(user.createdAt).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button onClick={() => handleEdit(user)}
                        disabled={user.email === 'admin@precisionpulse.com'}
                        className={`px-3 py-1 rounded text-xs font-semibold ${user.email === 'admin@precisionpulse.com' ? 'bg-slate-700 text-slate-500 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 text-white'}`}>
                        Edit
                      </button>
                      <button onClick={() => handleDelete(user.id)}
                        disabled={user.id === currentUser?.id || user.email === 'admin@precisionpulse.com'}
                        className={`px-3 py-1 rounded text-xs font-semibold ${user.id === currentUser?.id || user.email === 'admin@precisionpulse.com' ? 'bg-slate-700 text-slate-500 cursor-not-allowed' : 'bg-red-600 hover:bg-red-700 text-white'}`}>
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {/* Pagination */}
          {users.length > USER_PAGE_SIZE && (
            <div className="px-4 py-3 flex items-center justify-between border-t border-slate-700 bg-slate-700/20">
              <span className="text-slate-500 text-xs">Page {userPage} of {Math.ceil(users.length / USER_PAGE_SIZE)} · {users.length} users</span>
              <div className="flex gap-1">
                <button onClick={() => setUserPage(p => Math.max(1, p - 1))} disabled={userPage === 1}
                  className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 text-slate-300 rounded text-xs font-semibold">Prev</button>
                {Array.from({ length: Math.min(5, Math.ceil(users.length / USER_PAGE_SIZE)) }, (_, i) => {
                  const total = Math.ceil(users.length / USER_PAGE_SIZE);
                  const start = Math.max(1, Math.min(userPage - 2, total - 4));
                  const n = start + i;
                  return n <= total ? (
                    <button key={n} onClick={() => setUserPage(n)}
                      className={`px-2 py-1 rounded text-xs font-semibold ${
                        userPage === n ? 'bg-indigo-600 text-white' : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                      }`}>{n}</button>
                  ) : null;
                })}
                <button onClick={() => setUserPage(p => Math.min(Math.ceil(users.length / USER_PAGE_SIZE), p + 1))}
                  disabled={userPage === Math.ceil(users.length / USER_PAGE_SIZE)}
                  className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 text-slate-300 rounded text-xs font-semibold">Next</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl p-8 max-w-md w-full shadow-2xl">
            <h3 className="text-xl font-bold text-white mb-6">{editingId ? 'Edit User Role' : 'Add New User'}</h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Name</label>
                <input type="text" value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-indigo-500 focus:outline-none" required disabled={!!editingId} />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Email</label>
                <input type="email" value={formData.email} onChange={e => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-indigo-500 focus:outline-none" required disabled={!!editingId} />
              </div>
              {!editingId && (
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Password</label>
                  <input type="password" value={formData.password} onChange={e => setFormData({ ...formData, password: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-indigo-500 focus:outline-none" required />
                  <p className="text-slate-500 text-xs mt-1">Min 6 chars, uppercase, lowercase, number</p>
                </div>
              )}
              {errors.length > 0 && (
                <div className="p-3 bg-red-900/30 border border-red-700/40 rounded-lg">
                  {errors.map((e, i) => <p key={i} className="text-red-400 text-xs">{e}</p>)}
                </div>
              )}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Role</label>
                <select value={formData.role} onChange={e => setFormData({ ...formData, role: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-indigo-500 focus:outline-none">
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="submit" className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg text-sm">
                  {editingId ? 'Update' : 'Create'}
                </button>
                <button type="button" onClick={() => { setShowModal(false); setEditingId(null); setErrors([]); }}
                  className="flex-1 py-2.5 bg-slate-600 hover:bg-slate-700 text-white font-semibold rounded-lg text-sm">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
