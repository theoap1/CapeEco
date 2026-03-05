import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Building2, Mail, Lock, User, Loader2, AlertTriangle } from 'lucide-react';

export default function LoginPage() {
  const { login, register, isAuthenticated } = useAuth();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(email, password, fullName);
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Something went wrong';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (isAuthenticated) return <Navigate to="/" replace />;

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated mesh gradient background */}
      <div
        className="absolute inset-0 animate-gradient"
        style={{
          background: `
            radial-gradient(ellipse 80% 60% at 20% 30%, rgb(37 121 234 / 0.12), transparent 60%),
            radial-gradient(ellipse 70% 50% at 80% 70%, rgb(201 106 43 / 0.10), transparent 60%),
            radial-gradient(ellipse 90% 70% at 50% 50%, rgb(37 121 234 / 0.06), transparent 70%)
          `,
          backgroundSize: '200% 200%',
        }}
      />

      <div className="w-full max-w-md relative z-10">
        {/* Logo */}
        <div className="text-center mb-8 animate-fade-up delay-1">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-ocean-500/20 backdrop-blur-sm mb-4 border border-ocean-500/30 animate-glow">
            <Building2 className="w-8 h-8 text-ocean-400" />
          </div>
        </div>

        {/* Title */}
        <div className="text-center mb-8 animate-fade-up delay-2">
          <h1 className="text-3xl font-bold text-white tracking-tight">Siteline</h1>
        </div>

        {/* Taglines */}
        <div className="text-center mb-8 animate-fade-up delay-3">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-[0.2em]">
            Property Development Intelligence
          </p>
          <p className="text-sm text-gray-500 mt-2">
            South Africa's development data, unified.
          </p>
        </div>

        {/* Card */}
        <div className="bg-gray-800/50 backdrop-blur-xl border border-ocean-500/10 rounded-2xl shadow-2xl p-8 animate-fade-up delay-4">
          {/* Tabs */}
          <div className="flex mb-6 bg-gray-900/50 rounded-xl p-1">
            <button
              onClick={() => { setMode('login'); setError(''); }}
              className={`flex-1 py-2.5 text-sm font-semibold rounded-lg transition-all ${
                mode === 'login'
                  ? 'bg-ocean-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => { setMode('register'); setError(''); }}
              className={`flex-1 py-2.5 text-sm font-semibold rounded-lg transition-all ${
                mode === 'register'
                  ? 'bg-ocean-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Create Account
            </button>
          </div>

          {error && (
            <div className="mb-4 bg-red-900/30 border border-red-800/50 rounded-xl p-3 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
              <p className="text-sm text-red-300">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Full Name</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                  <input
                    type="text"
                    value={fullName}
                    onChange={e => setFullName(e.target.value)}
                    placeholder="Your name"
                    className="w-full pl-10 pr-4 py-2.5 bg-gray-900/50 border border-gray-700 rounded-xl text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-ocean-500 focus:border-transparent transition-all"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  placeholder="you@example.com"
                  className="w-full pl-10 pr-4 py-2.5 bg-gray-900/50 border border-gray-700 rounded-xl text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-ocean-500 focus:border-transparent transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  minLength={6}
                  placeholder={mode === 'register' ? 'Min 6 characters' : 'Your password'}
                  className="w-full pl-10 pr-4 py-2.5 bg-gray-900/50 border border-gray-700 rounded-xl text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-ocean-500 focus:border-transparent transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-ocean-600 to-ocean-500 hover:from-ocean-500 hover:to-ocean-400 text-white font-semibold rounded-xl shadow-lg shadow-ocean-600/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {mode === 'login' ? 'Signing in...' : 'Creating account...'}
                </>
              ) : (
                mode === 'login' ? 'Sign In' : 'Create Account'
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-gray-500 text-xs mt-6 animate-fade-up delay-5">
          Built on South African open government data
        </p>
      </div>
    </div>
  );
}
