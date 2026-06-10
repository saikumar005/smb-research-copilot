import React, { ButtonHTMLAttributes } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  loading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  loading = false,
  children,
  className = '',
  disabled,
  ...props
}) => {
  const getClassName = () => {
    const base = 'glow-btn-base';
    let specific = '';
    
    if (variant === 'primary') {
      specific = 'glow-btn';
    } else if (variant === 'secondary') {
      specific = 'glow-btn-secondary';
    } else if (variant === 'danger') {
      specific = 'glow-btn-danger';
    } else {
      specific = 'glow-btn-ghost';
    }
    
    return `${base} ${specific} ${className}`;
  };

  return (
    <button
      className={getClassName()}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span className="spinner-container">
          <span className="spinner-mini"></span>
          Loading...
        </span>
      ) : (
        children
      )}
    </button>
  );
};
