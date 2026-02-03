import { useEffect, useRef } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { verifyToken, login } from '@/api/auth';
import { useQueryClient } from '@tanstack/react-query';
import { useLocation } from '@tanstack/react-router';

// Add debug logging
const DEBUG = true;
const debugLog = (...args: unknown[]) => {
  if (DEBUG) console.log('[useAuthInitialization]', ...args);
};

export function useAuthInitialization() {
  const { token, user, isAuthenticated, setAuthenticated, setUser, logout, setToken, _hasHydrated } = useAuthStore();
  const queryClient = useQueryClient();
  const isInitializing = useRef(false);
  const location = useLocation();
  const isAuthRoute = ['/login', '/register'].includes(location.pathname);

  useEffect(() => {
    // Skip auto-login on landing page to avoid issues
    if (location.pathname === '/') {
      debugLog('Skipping auth initialization on landing page');
      isInitializing.current = true;
      return;
    }

    // Wait for hydration to complete before running auth logic
    // This prevents race conditions where we try to auto-login before localStorage is loaded
    if (!_hasHydrated) {
      debugLog('Waiting for auth store hydration');
      return;
    }

    // Proceed with auth initialization after hydration
    if (isInitializing.current) {
      debugLog('Auth initialization already in progress');
      return;
    }

    debugLog('Starting auth initialization', {
      hasToken: !!token,
      hasUser: !!user,
      isAuthenticated,
      pathname: location.pathname,
      isAuthRoute,
      _hasHydrated
    });

    isInitializing.current = true;

    // If we have a token but no user or not authenticated, verify it
    if (token && (!user || !isAuthenticated)) {
      debugLog('Verifying existing token');
      verifyToken(token)
        .then((verifiedUser) => {
          debugLog('Token verified successfully', verifiedUser);
          setUser(verifiedUser);
          setAuthenticated(true);
        })
        .catch((err) => {
          debugLog('Token verification failed', err);
          // Token is invalid, clear auth state
          logout();
        })
        .finally(() => {
          isInitializing.current = false;
        });
    } else if (!token && !user && !isAuthRoute) {
      // No token and no user - auto-login as Gain Smith for demo purposes
      // Skip auto-login if on auth routes to avoid interfering with manual login
      debugLog('No auth found, starting auto-login');
      login('gainsmith@gainsly.com', 'password123')
        .then((response) => {
          debugLog('Login successful, got token');
          setToken(response.access_token);
          // Verify token to get complete user data from backend
          return verifyToken(response.access_token);
        })
        .then((verifiedUser) => {
          debugLog('Auto-login complete, user authenticated', verifiedUser);
          setUser(verifiedUser);
          setAuthenticated(true);
          // Invalidate all queries to force refetch with new auth
          queryClient.invalidateQueries();
        })
        .catch((err) => {
          debugLog('Auto-login failed:', err);
          console.error('Auto-login failed:', err);
        })
        .finally(() => {
          isInitializing.current = false;
        });
    } else {
      debugLog('Auth state already valid, skipping initialization');
      isInitializing.current = false;
    }
  }, [token, user, isAuthenticated, setAuthenticated, setUser, logout, setToken, queryClient, _hasHydrated, isAuthRoute, location.pathname]);

  // Safety timeout: Force hydration flag if it doesn't complete after 1 second
  useEffect(() => {
    const timeout = setTimeout(() => {
      if (!_hasHydrated) {
        console.warn('Auth store hydration timeout - forcing hydration flag');
        const store = useAuthStore.getState();
        store.setHydrated();
      }
    }, 1000);

    return () => clearTimeout(timeout);
  }, [_hasHydrated]);
}
