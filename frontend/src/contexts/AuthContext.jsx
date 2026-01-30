import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const api = axios.create({ baseURL: '/api' });

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('capeeco_token'));
  const [loading, setLoading] = useState(true);

  // On mount, validate existing token
  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    api.get('/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setUser(r.data))
      .catch(() => {
        // Token expired or invalid
        localStorage.removeItem('capeeco_token');
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    const { access_token, user: userData } = res.data;
    localStorage.setItem('capeeco_token', access_token);
    setToken(access_token);
    setUser(userData);
    return userData;
  }, []);

  const register = useCallback(async (email, password, fullName) => {
    const res = await api.post('/auth/register', { email, password, full_name: fullName });
    const { access_token, user: userData } = res.data;
    localStorage.setItem('capeeco_token', access_token);
    setToken(access_token);
    setUser(userData);
    return userData;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('capeeco_token');
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
