import { useState } from 'react';

const API_BASE = '/api';

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Please enter both username and password.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password: password.trim() }),
      });
      const data = await res.json();

      if (res.ok && data.status === 'success') {
        localStorage.setItem('token', data.token);
        onLogin(data.user, data.token);
      } else {
        setError(data.message || 'Login failed. Check your credentials.');
      }
    } catch (err) {
      setError('Could not connect to server. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">
            <svg viewBox="0 0 40 40" className="logo-icon">
              <rect x="4" y="20" width="32" height="16" rx="2" fill="#0F2B46" />
              <rect x="8" y="10" width="24" height="14" rx="2" fill="#1a4a6e" />
              <rect x="12" y="4" width="16" height="10" rx="2" fill="#2d6a9f" />
              <circle cx="20" cy="28" r="3" fill="#38bdf8" />
            </svg>
          </div>
          <h1>Enterprise Bank Corp.</h1>
          <p className="login-subtitle">AI Report Designer</p>
        </div>

        <form onSubmit={handleLogin} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              autoComplete="username"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              autoComplete="current-password"
              disabled={loading}
            />
          </div>

          {error && <div className="login-error">{error}</div>}

          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? (
              <span className="spinner"></span>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <div className="login-footer">
          <p>Demo Credentials:</p>
          <div className="demo-creds">
            <span>admin / admin123</span>
            <span>analyst_joy / analyst123</span>
            <span>manager_bob / manager123</span>
          </div>
        </div>
      </div>
    </div>
  );
}
