import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { UserResponse } from '@/api/auth';

interface AuthState {
  token: string | null;
  user: UserResponse | null;
  isAuthenticated: boolean;
  _hasHydrated: boolean;
  
  setToken: (token: string | null) => void;
  setUser: (user: UserResponse | null) => void;
  setAuthenticated: (isAuthenticated: boolean) => void;
  logout: () => void;
  setHydrated: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      _hasHydrated: false,
      
      setToken: (token) => set({ token }),
      setUser: (user) => set({ user }),
      setAuthenticated: (isAuthenticated) => set({ isAuthenticated }),
      logout: () => set({ token: null, user: null, isAuthenticated: false }),
      setHydrated: () => set({ _hasHydrated: true }),
    }),
    {
      name: 'alloy-auth-storage',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        // Mark hydration as complete - this runs after rehydration
        state?.setHydrated();
      },
    }
  )
);
