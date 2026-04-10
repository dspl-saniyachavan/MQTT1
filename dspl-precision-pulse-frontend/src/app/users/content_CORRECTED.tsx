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
      const newUser: User = {
        id: data.id?.toString() || data.user_id?.toString() || '',
        email: data.email || '',
        name: data.name || '',
        role: data.role || 'user',
        isActive: data.is_active !== false,
        createdAt: data.created_at || new Date().toISOString(),
      };
      setUsers(prev => prev.some(u => u.email === newUser.email) ? prev : [...prev, newUser]);
    });

    socketIOService.on('user_updated', (data: any) => {
      setUsers(prev => prev.map(u =>
        u.id === data.id?.toString() || u.email === data.email
          ? {
              ...u,
              name: data.name || u.name,
              role: data.role || u.role,
              isActive: data.is_active !== undefined ? data.is_active : u.isActive,
              id: data.id?.toString() || u.id
            }
          : u
      ));
    });

    socketIOService.on('user_deleted', (data: any) => {
      setUsers(prev => prev.filter(u => u.id !== data.id?.toString() && u.email !== data.email));
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
      const token = localStorage.getItem('token');
      const method = editingId ? 'PUT' : 'POST';
      const url = editingId ? `${BACKEND}/api/users/${editingId}` : `${BACKEND}/api/users`;
      const body = editingId ? { role: formData.role } : formData;
      
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      
      if (res.ok) {
        if (editingId) {
          const updatedUser = await res.json();
          setUsers(users.map(u => u.id === editingId ? {
            ...u,
            role: updatedUser.role,
            name: updatedUser.name,
            isActive: updatedUser.is_active
          } : u));
        } else {
          const newUser = await res.json();
          setUsers([...users, {
            id: newUser.id.toString(),
            email: newUser.email,
            name: newUser.name,
            role: newUser.role,
            isActive: newUser.is_active,
            createdAt: newUser.created_at
          }]);
        }
        
        setShowModal(false);
        setFormData({ name: '', email: '', password: '', role: 'user' });
        setEditingId(null);
        setErrors([]);
      } else {
        const data = await res.json();
        setErrors([data.error || (editingId ? 'Failed to update user' : 'Failed to create user')]);
      }
    } catch {
      setErrors(['Network error']);
    }
  };

  const handleEdit = (user: User) => {
    setFormData({ name: user.name, email: user.email, password: '', role: user.role });
    setEditingId(user.id);
    setShowModal(true);
  };

  const handleDelete = async (id: string) => {
    if (id === currentUser?.id) { alert('You cannot delete yourself!'); return; }
    if (!confirm('Delete this user?')) return;
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${BACKEND}/api/users/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setUsers(users.filter(u => u.id !== id));
      else alert('Failed to delete user');
    } catch { alert('Error deleting user'); }
  };

  if (!currentUser) return null;

  const totalUsers = users.length;
  const adminCount = users.filter(u => u.role === 'admin').length;
  const activeCount = users.filter(u => u.isActive).length;
  const onlineCount = users.filter(u => isOnline(u.email)).length;

  return (
    <div className="min-h-screen page-container">
      <div className="sticky top-0 z-50" style={{background:"linear-gradient(90deg,#4892e1,#6dadf0)",boxShadow:"0 2px 12px rgba(72,146,225,0.2)"}}>
        <div className="px-4 sm:px-8 py-4">
          <h1 className="text-lg sm:text-2xl font-bold text-white">User Management</h1>
          <p className="text-xs sm:text-sm text-white/75">Add, edit, or remove user accounts</p>
        </div>
      </div>

      <div className="px-4 sm:px-8 lg:px-20 py-12">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
          <div>
            <h2 className="text-2xl sm:text-4xl font-bold text-white mb-2">Manage Users</h2>
            <p className="text-sm sm:text-lg text-gray-500">Add, edit, or remove user accounts</p>
          </div>
          <button
            onClick={() => { setShowModal(true); setEditingId(null); setFormData({ name: '', email: '', password: '', role: 'user' }); }}
            className="w-full sm:w-auto px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-gray-800 font-semibold rounded-lg"
          >
            + Add User
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Total Users', value: totalUsers, color: 'text-indigo-400', bg: 'bg-indigo-900/20 border-indigo-700/40' },
            { label: 'Admins', value: adminCount, color: 'text-purple-600', bg: 'bg-purple-900/20 border-purple-700/40' },
            { label: 'Active Accounts', value: activeCount, color: 'text-emerald-400', bg: 'bg-emerald-900/20 border-emerald-700/40' },
            { label: 'Currently Online', value: onlineCount, color: 'text-sky-400', bg: 'bg-sky-900/20 border-sky-700/40' },
          ].map(({ label, value, color, bg }) => (
            <div key={label} className={`rounded-xl border p-4 ${bg}`}>
              <div className={`text-3xl font-bold ${color}`}>{value}</div>
              <div className="text-gray-500 text-xs mt-1">{label}</div>
            </div>
          ))}
        </div>

        <div className="section-card rounded-xl overflow-hidden overflow-x-auto">
          <table className="w-full min-w-[600px] text-sm">
            <thead className="border-b border-blue-100 bg-blue-50/50">
              <tr>
                <th className="px-4 py-3 text-left text-gray-600 font-semibold">Name</th>
                <th className="px-4 py-3 text-left text-gray-600 font-semibold">Email</th>
                <th className="px-4 py-3 text-left text-gray-600 font-semibold">Role</th>
                <th className="px-4 py-3 text-left text-gray-600 font-semibold">Status</th>
                <th className="px-4 py-3 text-left text-gray-600 font-semibold">Created</th>
                <th className="px-4 py-3 text-right text-gray-600 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60">
              {users.slice((userPage - 1) * USER_PAGE_SIZE, userPage * USER_PAGE_SIZE).map((user) => {
                const online = isOnline(user.email);
                return (
                  <tr key={user.id} className="hover:bg-blue-50/30 transition-colors">
                    <td className="px-4 py-3 text-gray-700 font-medium">{user.name}</td>
                    <td className="px-4 py-3 text-gray-500">{user.email}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${user.role === 'admin' ? 'bg-purple-900/40 text-purple-300' : 'bg-blue-900/40 text-blue-300'}`}>
                        {user.role.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold ${online ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${online ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
                        {online ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{new Date(user.createdAt).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button onClick={() => handleEdit(user)}
                        disabled={user.email === 'admin@precisionpulse.com'}
                        className={`px-3 py-1 rounded text-xs font-semibold ${user.email === 'admin@precisionpulse.com' ? 'bg-slate-700 text-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 text-white'}`}>
                        Edit
                      </button>
                      <button onClick={() => handleDelete(user.id)}
                        disabled={user.id === currentUser?.id || user.email === 'admin@precisionpulse.com'}
                        className={`px-3 py-1 rounded text-xs font-semibold ${user.id === currentUser?.id || user.email === 'admin@precisionpulse.com' ? 'bg-slate-700 text-gray-400 cursor-not-allowed' : 'bg-red-600 hover:bg-red-700 text-white'}`}>
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {users.length > USER_PAGE_SIZE && (
            <div className="px-4 py-3 flex items-center justify-between border-t border-blue-100 bg-blue-50/50">
              <span className="text-gray-400 text-xs">Page {userPage} of {Math.ceil(users.length / USER_PAGE_SIZE)} · {users.length} users</span>
              <div className="flex gap-1">
                <button onClick={() => setUserPage(p => Math.max(1, p - 1))} disabled={userPage === 1}
                  className="px-3 py-1 bg-blue-100 hover:bg-blue-200 disabled:bg-white disabled:text-gray-400 text-gray-600 rounded text-xs font-semibold">Prev</button>
                {Array.from({ length: Math.min(5, Math.ceil(users.length / USER_PAGE_SIZE)) }, (_, i) => {
                  const total = Math.ceil(users.length / USER_PAGE_SIZE);
                  const start = Math.max(1, Math.min(userPage - 2, total - 4));
                  const n = start + i;
                  return n <= total ? (
                    <button key={n} onClick={() => setUserPage(n)}
                      className={`px-2 py-1 rounded text-xs font-semibold ${
                        userPage === n ? 'bg-teal-600 text-white' : 'bg-blue-100 hover:bg-blue-200 text-gray-600'
                      }`}>{n}</button>
                  ) : null;
                })}
                <button onClick={() => setUserPage(p => Math.min(Math.ceil(users.length / USER_PAGE_SIZE), p + 1))}
                  disabled={userPage === Math.ceil(users.length / USER_PAGE_SIZE)}
                  className="px-3 py-1 bg-blue-100 hover:bg-blue-200 disabled:bg-white disabled:text-gray-400 text-gray-600 rounded text-xs font-semibold">Next</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-6">
          <div className="bg-white border border-blue-100 rounded-2xl p-8 max-w-md w-full shadow-2xl">
            <h3 className="text-xl font-bold text-white mb-6">{editingId ? 'Edit User Role' : 'Add New User'}</h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Name</label>
                <input type="text" value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-700 border border-blue-200 rounded-lg text-gray-800 text-sm focus:border-teal-500 focus:outline-none" required disabled={!!editingId} />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Email</label>
                <input type="email" value={formData.email} onChange={e => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-700 border border-blue-200 rounded-lg text-gray-800 text-sm focus:border-teal-500 focus:outline-none" required disabled={!!editingId} />
              </div>
              {!editingId && (
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Password</label>
                  <input type="password" value={formData.password} onChange={e => setFormData({ ...formData, password: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-700 border border-blue-200 rounded-lg text-gray-800 text-sm focus:border-teal-500 focus:outline-none" required />
                  <p className="text-gray-400 text-xs mt-1">Min 6 chars, uppercase, lowercase, number</p>
                </div>
              )}
              {errors.length > 0 && (
                <div className="p-3 bg-red-900/30 border border-red-700/40 rounded-lg">
                  {errors.map((e, i) => <p key={i} className="text-red-400 text-xs">{e}</p>)}
                </div>
              )}
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Role</label>
                <select value={formData.role} onChange={e => setFormData({ ...formData, role: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-700 border border-blue-200 rounded-lg text-gray-800 text-sm focus:border-teal-500 focus:outline-none">
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="submit" className="flex-1 py-2.5 btn-primary text-gray-800 font-semibold rounded-lg text-sm">
                  {editingId ? 'Update' : 'Create'}
                </button>
                <button type="button" onClick={() => { setShowModal(false); setEditingId(null); setErrors([]); }}
                  className="flex-1 py-2.5 bg-slate-600 hover:bg-blue-100 text-gray-800 font-semibold rounded-lg text-sm">
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
