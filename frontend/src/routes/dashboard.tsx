import { createFileRoute } from '@tanstack/react-router';
import { Dashboard } from '@/components/layout/dashboard';

export const Route = createFileRoute('/dashboard')({
  component: Dashboard,
});
