import { createFileRoute } from '@tanstack/react-router';
import { LandingPage } from '@/components/landing/LandingPage';
import '@/styles/landing.css';

export const Route = createFileRoute('/')({
  component: LandingPage,
});
