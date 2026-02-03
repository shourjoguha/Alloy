import { useEffect, useRef } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { verifyToken, login } from '@/api/auth';
import { useQueryClient } from '@tanstack/react-query';
import { useLocation } from '@tanstack/react-router';

export function useAuthInitialization() {
  const { token, user, isAuthenticated, setAuthenticated, setUser, logout, setToken, _hasHydrated } = useAuthStore();
  const queryClient = useQueryClient();
  const isInitializing = useRef(false);
  const location = useLocation();
  const isAuthRoute = ['/login', '/register'].includes(location.pathname);

  useEffect(() => {
    // Skip auto-login on landing page to avoid issues
    if (location.pathname === '/') {
      isInitializing.current = true;
      return;
    }

    // Proceed with auth initialization regardless of hydration status
    // This prevents app from hanging if hydration is delayed
    if (isInitializing.current) {
      return;
    }

    isInitializing.current = true;

    // If we have a token but no user or not authenticated, verify it
    if (token && (!user || !isAuthenticated)) {
      verifyToken(token)
        .then((verifiedUser) => {
          setUser(verifiedUser);
          setAuthenticated(true);
        })
        .catch(() => {
          // Token is invalid, clear auth state
          logout();
        })
        .finally(() => {
          isInitializing.current = false;
        });
    } else if (!token && !user && !isAuthRoute) {
      // No token and no user - auto-login as Gain Smith for demo purposes
      // Skip auto-login if on auth routes to avoid interfering with manual login
      login('gainsmith@gainsly.com', 'gainsmith123')
        .then((response) => {
          setToken(response.access_token);
          // Verify token to get complete user data from backend
          return verifyToken(response.access_token);
        })
        .then((verifiedUser) => {
          setUser(verifiedUser);
          setAuthenticated(true);
          // Invalidate all queries to force refetch with new auth
          queryClient.invalidateQueries();
        })
        .catch((err) => {
          console.error('Auto-login failed:', err);
        })
        .finally(() => {
          isInitializing.current = false;
        });
    } else {
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
