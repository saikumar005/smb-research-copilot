import axios from 'axios';

// Get backend API URL from environment, fallback to standard docker port address
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to attach JWT token to all outgoing calls
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle session expiration (401 errors)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      logger_session_expiry();
    }
    return Promise.reject(error);
  }
);

function logger_session_expiry() {
  console.warn("Session expired or token invalid. Clearing auth credentials.");
  localStorage.removeItem('token');
  // Only redirect if we are not already on login or signup views
  const currentPath = window.location.pathname;
  if (currentPath !== '/login' && currentPath !== '/signup' && currentPath !== '/forgot-password' && currentPath !== '/reset-password') {
    window.location.href = '/login?expired=true';
  }
}
