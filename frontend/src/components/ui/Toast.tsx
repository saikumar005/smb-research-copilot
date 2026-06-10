import React, { useEffect } from 'react';
import { X } from 'lucide-react';

export interface ToastMessage {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface ToastProps {
  message: string;
  type?: 'success' | 'error' | 'info';
  onClose: () => void;
  duration?: number;
}

export const Toast: React.FC<ToastProps> = ({
  message,
  type = 'info',
  onClose,
  duration = 4000
}) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, duration);
    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const getToastClass = () => {
    return `toast-card toast-${type} animate-fade-in`;
  };

  return (
    <div className={getToastClass()}>
      <span className="toast-text">{message}</span>
      <button className="toast-close-btn" onClick={onClose} aria-label="Close alert">
        <X size={16} />
      </button>
    </div>
  );
};
