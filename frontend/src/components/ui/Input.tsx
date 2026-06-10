import React, { InputHTMLAttributes, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  id,
  type = 'text',
  className = '',
  ...props
}) => {
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = type === 'password';

  return (
    <div className="form-group">
      {label && <label htmlFor={id}>{label}</label>}
      <div style={{ position: 'relative', width: '100%' }}>
        <input
          id={id}
          type={isPassword && showPassword ? 'text' : type}
          className={`text-input ${error ? 'input-error' : ''} ${className}`}
          style={isPassword ? { paddingRight: '46px' } : {}}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            tabIndex={-1}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            style={{
              position: 'absolute',
              right: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '4px',
              transition: 'color 0.2s',
              outline: 'none',
            }}
            onMouseOver={(e) => (e.currentTarget.style.color = 'var(--accent-purple)')}
            onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
            onFocus={(e) => (e.currentTarget.style.color = 'var(--accent-purple)')}
            onBlur={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
          >
            {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
          </button>
        )}
      </div>
      {error && <span className="error-message">{error}</span>}
    </div>
  );
};

