import React, { useState } from 'react';

const LoginPage = ({ onLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleLogin = () => {
    setError(null);
    if (!email || !password) {
      setError('Enter your EQ Bank credentials');
      return;
    }

    // Lightweight local check only; no backend auth wired yet.
    const allowedDemo =
      (email.toLowerCase() === 'demo@eqbank.com' && password === 'eqbank123!') ||
      email.toLowerCase().endsWith('@eqbank.com');

    if (!allowedDemo) {
      setError('Invalid credentials. Use demo@eqbank.com / eqbank123!');
      return;
    }

    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      onLogin({
        email,
        name: email.split('@')[0],
        role: 'Specialist',
      });
    }, 350);
  };

  const handleDemo = () => {
    setEmail('demo@eqbank.com');
    setPassword('eqbank123!');
    setError(null);
  };

  return (
    <div className="login-layout">
      <div className="login-left">
        <div className="login-overlay">
          <div className="pill pill-ghost">EQ Bank · Compliance</div>
          <h1>EQ Bank Customer Screening Portal</h1>
          <p className="login-lead">Human-in-the-loop AML/KYC orchestration</p>

          <div className="login-feature">
            <div className="login-icon">🛡️</div>
            <div>
              <div className="login-feature-title">AI-powered screening</div>
              <div className="login-feature-sub">Automated checks with explainability</div>
            </div>
          </div>
          <div className="login-feature">
            <div className="login-icon">👤</div>
            <div>
              <div className="login-feature-title">Specialist overrides</div>
              <div className="login-feature-sub">Manual review for flagged cases</div>
            </div>
          </div>
          <div className="login-feature">
            <div className="login-icon">⚡</div>
            <div>
              <div className="login-feature-title">Real-time tracking</div>
              <div className="login-feature-sub">Monitor every step of the workflow</div>
            </div>
          </div>
        </div>
      </div>

      <div className="login-right">
        <div className="login-card">
          <div className="login-brand">
            <h2>Welcome back</h2>
            <p>Sign in to the screening console</p>
          </div>

          {error && <div className="error" style={{ marginBottom: 12 }}>{error}</div>}

          <div className="form-group">
            <label>Username</label>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your username"
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <div className="password-field">
              <input
                className="input"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
              />
              <button
                type="button"
                className="link-btn"
                onClick={() => setShowPassword((v) => !v)}
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          <div className="login-actions">
            <button className="button button-success" onClick={handleLogin} disabled={loading}>
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
            <button className="button button-warning" onClick={handleDemo} disabled={loading}>
              Demo login
            </button>
          </div>

          <div className="login-footnote">EQ Bank AML/KYC Orchestration Platform</div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;

