import React from 'react';

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  fullScreen?: boolean;
}

export const Spinner: React.FC<SpinnerProps> = ({
  size = 'md',
  fullScreen = false
}) => {
  const getSpinnerClass = () => {
    return `spinner spinner-${size}`;
  };

  if (fullScreen) {
    return (
      <div className="spinner-overlay">
        <div className={getSpinnerClass()}></div>
        <p className="spinner-text">Analyzing database states...</p>
      </div>
    );
  }

  return <div className={getSpinnerClass()}></div>;
};
