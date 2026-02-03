import axios, { AxiosError, AxiosInstance } from 'axios';
import { useAuthStore } from '@/stores/auth-store';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// Debug logging
const DEBUG_API = true;
const debugLog = (...args: unknown[]) => {
  if (DEBUG_API) console.log('[apiClient]', ...args);
};

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    const isAuthenticated = useAuthStore.getState().isAuthenticated;
    
    debugLog('Request:', {
      method: config.method?.toUpperCase(),
      url: config.url,
      hasToken: !!token,
      isAuthenticated,
      baseURL: config.baseURL,
      fullUrl: `${config.baseURL}${config.url}`
    });
    
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    } else {
      debugLog('⚠️ Request made without token');
    }
    return config;
  },
  (error) => {
    debugLog('Request interceptor error:', error);
    return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  (response) => {
    debugLog('Response:', {
      status: response.status,
      url: response.config.url,
      dataKeys: Object.keys(response.data || {})
    });
    return response;
  },
  (error: AxiosError) => {
    if (error.response) {
      const status = error.response.status;
      
      debugLog('Response error:', {
        status,
        url: error.config?.url,
        data: error.response.data,
        message: error.message
      });
      
      if (status === 401) {
        useAuthStore.getState().logout();
        console.error('Unauthorized request');
      } else if (status === 403) {
        console.error('Forbidden request');
      } else if (status === 404) {
        console.error('Resource not found');
      } else if (status >= 500) {
        console.error('Server error');
      }
    } else if (error.request) {
      debugLog('Network error - no response received:', error.message);
      console.error('Network error - no response received');
    } else {
      debugLog('Request setup error:', error.message);
      console.error('Request setup error:', error.message);
    }
    
    return Promise.reject(error);
  }
);

export async function* streamSSE(url: string, body: unknown): AsyncGenerator<string> {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') {
          return;
        }
        yield data;
      }
    }
  }
}

export default apiClient;
