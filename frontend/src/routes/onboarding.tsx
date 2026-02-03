import { createFileRoute, redirect } from '@tanstack/react-router';
import { OnboardingContainer } from '@/components/onboarding/OnboardingContainer';
import { useAuthStore } from '@/stores/auth-store';

export const Route = createFileRoute('/onboarding')({
  beforeLoad: () => {
    const { isAuthenticated, hasCompletedOnboarding } = useAuthStore.getState();

    // Check if user is authenticated
    if (!isAuthenticated) {
      throw redirect({
        to: '/login',
      });
    }

    // Check if user has already completed onboarding
    if (hasCompletedOnboarding) {
      throw redirect({
        to: '/dashboard',
      });
    }
  },
  component: OnboardingContainer,
});