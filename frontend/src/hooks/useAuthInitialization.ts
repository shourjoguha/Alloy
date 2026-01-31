import { useEffect } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { verifyToken, login } from '@/api/auth';
import { useQueryClient } from '@tanstack/react-query';

export function useAuthInitialization() {
  const { token, user, isAuthenticated, setAuthenticated, setUser, logout, setToken } = useAuthStore();
  const queryClient = useQueryClient();

  useEffect(() => {
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
        });
    }
    // Auto-login disabled for onboarding testing
    // else if (!token && !user) {
    //   // No token and no user - auto-login as Gain Smith for demo purposes
    //   login('gainsmith@gainsly.com', 'gainsmith123')
    //     .then((response) => {
    //       setToken(response.access_token);
    //       // Verify token to get complete user data from backend
    //       return verifyToken(response.access_token);
    //     })
    //     .then((verifiedUser) => {
    //       setUser(verifiedUser);
    //       setAuthenticated(true);
    //       // Invalidate all queries to force refetch with new auth
    //       queryClient.invalidateQueries();
    //     })
    //     .catch((err) => {
    //       console.error('Auto-login failed:', err);
    //     });
    // }
  }, [token, user, isAuthenticated, setAuthenticated, setUser, logout, setToken, queryClient]);
}
