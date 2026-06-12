import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Brain } from 'lucide-react';
import { apiClient } from '../api/client';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';

export const Signup: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let attempts = 0;
    const initGoogleBtn = () => {
      const g = (window as any).google;
      if (!g?.accounts?.id) {
        if (attempts < 30) {
          attempts++;
          setTimeout(initGoogleBtn, 100);
        }
        return;
      }

      const client_id = import.meta.env.VITE_GOOGLE_CLIENT_ID;
      if (!client_id) {
        console.warn("VITE_GOOGLE_CLIENT_ID is not configured");
        return;
      }

      g.accounts.id.initialize({
        client_id: client_id,
        callback: async (response: any) => {
          if (!response.credential) return;
          setGoogleLoading(true);
          setError(null);
          try {
            const res = await apiClient.post('/auth/google', {
              id_token: response.credential,
            });
            localStorage.setItem('token', res.data.access_token);
            navigate('/chat');
          } catch (err: unknown) {
            const msg =
              (err as { response?: { data?: { detail?: string } } })
                ?.response?.data?.detail ??
              'Google authentication failed. Please try again.';
            setError(msg);
          } finally {
            setGoogleLoading(false);
          }
        },
        auto_select: false,
        use_fedcm: false, // Prevents FedCM NetworkError/blocking issues on localhost
      });

      const btnContainer = document.getElementById("google-signin-button");
      if (btnContainer) {
        g.accounts.id.renderButton(
          btnContainer,
          {
            theme: "outline",
            size: "large",
            width: btnContainer.clientWidth || 320,
            text: "signup_with",
            shape: "rectangular",
          }
        );
      }
    };

    initGoogleBtn();
  }, [navigate]);

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

        {/* Google SSO Button Container */}
        <div
          id="google-signin-button"
          style={{
            display: 'flex',
            justifyContent: 'center',
            width: '100%',
            minHeight: '44px',
            marginBottom: '8px',
          }}
        >
          {googleLoading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)' }}>
              <div className="spinner" style={{ width: '16px', height: '16px', borderColor: 'rgba(255, 255, 255, 0.15)', borderTopColor: '#ffffff' }} />
              <span>Verifying with Google…</span>
            </div>
          )}
        </div>

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
