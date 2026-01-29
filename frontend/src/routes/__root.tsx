import { createRootRoute, Outlet, useLocation, useNavigate } from '@tanstack/react-router';
import { TanStackRouterDevtools } from '@tanstack/router-devtools';
import { AppShell } from '@/components/layout/app-shell';
import { useAuthStore } from '@/stores/auth-store';
import { useAuthInitialization } from '@/hooks/useAuthInitialization';
import { useEffect } from 'react';

export const Route = createRootRoute({
  component: RootComponent,
});

function RootComponent() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const isAuthRoute = ['/login', '/register'].includes(location.pathname);
  const isLandingRoute = location.pathname === '/';
  const isPublicRoute = isAuthRoute || isLandingRoute;
  
  useAuthInitialization();

  useEffect(() => {
    if (!isAuthenticated && !isPublicRoute && !isAuthRoute) {
      navigate({ to: '/login' } as any);
    } else if (isAuthenticated && (isLandingRoute || isAuthRoute)) {
      navigate({ to: '/dashboard' } as any);
    }
  }, [isAuthenticated, isPublicRoute, isAuthRoute, isLandingRoute, navigate]);

  return (
    <>
      {isLandingRoute ? (
        <Outlet />
      ) : isAuthRoute ? (
        <main className="min-h-dvh bg-background">
          <Outlet />
        </main>
      ) : (
        <AppShell>
          <Outlet />
        </AppShell>
      )}
      {import.meta.env.DEV && <TanStackRouterDevtools position="bottom-right" />}
    </>
  );
}
