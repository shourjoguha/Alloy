import { createRootRoute, Outlet, useLocation, useNavigate } from '@tanstack/react-router';
import { TanStackRouterDevtools } from '@tanstack/router-devtools';
import { AppShell } from '@/components/layout/app-shell';
import { useAuthStore } from '@/stores/auth-store';
import { useAuthInitialization } from '@/hooks/useAuthInitialization';
import { useEffect } from 'react';

// Add debug logging
const DEBUG = true;
const debugLog = (...args: unknown[]) => {
  if (DEBUG) console.log('[RootRoute]', ...args);
};

export const Route = createRootRoute({
  component: RootComponent,
});

function RootComponent() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, _hasHydrated } = useAuthStore();
  const isAuthRoute = ['/login', '/register'].includes(location.pathname);
  const isLandingRoute = location.pathname === '/';
  const isPublicRoute = isAuthRoute || isLandingRoute;
  
  useAuthInitialization();

  useEffect(() => {
    debugLog('Route protection check', {
      _hasHydrated,
      isAuthenticated,
      isPublicRoute,
      isAuthRoute,
      pathname: location.pathname
    });

    // Only redirect after hydration is complete and auth check fails
    if (_hasHydrated && !isAuthenticated && !isPublicRoute && !isAuthRoute) {
      debugLog('Redirecting to login - not authenticated');
      navigate({ to: '/login' });
    }
  }, [_hasHydrated, isAuthenticated, isPublicRoute, isAuthRoute, navigate, location.pathname]);

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
