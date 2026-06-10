import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Brain } from 'lucide-react';
import { apiClient } from '../api/client';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { useGoogleAuth } from '../hooks/useGoogleAuth';

// Google 'G' logo as an inline SVG component
const GoogleLogo: React.FC = () => (
  <svg className="google-logo" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
);

export const Signup: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { signInWithGoogle } = useGoogleAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await apiClient.post('/auth/signup', { name, email, password });
      navigate('/login?signup=success');
    } catch (err: unknown) {
      console.error(err);
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'An error occurred during registration. Please verify details.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignUp = async () => {
    setError(null);
    setGoogleLoading(true);

    try {
      const result = await signInWithGoogle();
      localStorage.setItem('token', result.access_token);
      navigate('/chat');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Google sign-up failed. Please try again.';
      setError(msg);
    } finally {
      setGoogleLoading(false);
    }
  };

  const isAnyLoading = loading || googleLoading;

  return (
    <div className="auth-wrapper">
      <div className="auth-card glass-panel animate-fade-in">
        <div className="auth-header">
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '12px' }}>
            <div className="welcome-logo-badge">
              <Brain size={32} />
            </div>
          </div>
          <h2>Create Account</h2>
          <p>Get started with the Business Research Copilot</p>
        </div>

        {error && (
          <div className="toast-card toast-error" style={{ maxWidth: 'none', margin: '0' }}>
            <span className="toast-text">{error}</span>
          </div>
        )}

        {/* Google SSO Button */}
        <button
          id="btn-google-signup"
          className="google-btn"
          onClick={handleGoogleSignUp}
          disabled={isAnyLoading}
          type="button"
        >
          {googleLoading ? (
            <div className="spinner" />
          ) : (
            <GoogleLogo />
          )}
          <span>{googleLoading ? 'Signing up with Google…' : 'Sign up with Google'}</span>
        </button>

        {/* Divider */}
        <div className="auth-divider">
          <span className="auth-divider-label">or register with email</span>
        </div>

        {/* Email / Password Registration Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <Input
            id="name"
            label="Full Name"
            type="text"
            placeholder="John Doe"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />

          <Input
            id="email"
            label="Email Address"
            type="email"
            placeholder="john@company.com"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <Input
            id="password"
            label="Password"
            type="password"
            placeholder="••••••••"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <Button type="submit" loading={loading} disabled={isAnyLoading} style={{ width: '100%', marginTop: '8px' }}>
            Create Account
          </Button>
        </form>

        <div className="auth-footer">
          Already have an account?{' '}
          <Link to="/login" style={{ fontWeight: 600 }}>
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
};
export default Signup;
