import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { UserResponse } from '@/api/auth';

interface AuthState {
  token: string | null;
  user: UserResponse | null;
  isAuthenticated: boolean;
  hasCompletedOnboarding: boolean;
  
  setToken: (token: string | null) => void;
  setUser: (user: UserResponse | null) => void;
  setAuthenticated: (isAuthenticated: boolean) => void;
  setHasCompletedOnboarding: (hasCompletedOnboarding: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      hasCompletedOnboarding: false,
      
      setToken: (token) => set({ token }),
      setUser: (user) => set({ user, hasCompletedOnboarding: user?.has_completed_onboarding ?? false }),
      setAuthenticated: (isAuthenticated) => set({ isAuthenticated }),
      setHasCompletedOnboarding: (hasCompletedOnboarding) => set({ hasCompletedOnboarding }),
      logout: () => set({ token: null, user: null, isAuthenticated: false, hasCompletedOnboarding: false }),
    }),
    {
      name: 'alloy-auth-storage',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        hasCompletedOnboarding: state.hasCompletedOnboarding,
      }),
    }
  )
);
