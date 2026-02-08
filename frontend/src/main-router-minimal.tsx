import { createRoot } from 'react-dom/client';
import { RouterProvider, createRouter, createRootRoute, Outlet, createFileRoute } from '@tanstack/react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

console.log('=== Minimal Router Test: Starting ===');

// Create a minimal root route without auth
const rootRoute = createRootRoute({
  component: () => (
    <div style={{ padding: '20px', color: 'white', backgroundColor: 'darkblue' }}>
      <h1>Minimal Root Route</h1>
      <Outlet />
    </div>
  ),
});

// Create a minimal index route
const indexRoute = createFileRoute('/')({
  component: () => (
    <div style={{ padding: '20px', color: 'white', backgroundColor: 'green' }}>
      <h2>Index Route - Minimal Router Working!</h2>
    </div>
  ),
});

const routeTree = rootRoute.addChildren([indexRoute]);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60,
      gcTime: 1000 * 60 * 5,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

console.log('=== Minimal Router Test: Creating router ===');

const router = createRouter({
  routeTree,
  context: {
    queryClient,
  },
});

console.log('=== Minimal Router Test: Router created ===');

const rootElement = document.getElementById('root');

if (rootElement) {
  try {
    const root = createRoot(rootElement);
    console.log('=== Minimal Router Test: Root created ===');

    root.render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    );
    console.log('=== Minimal Router Test: Render complete ===');
  } catch (error) {
    console.error('=== Minimal Router Test: Render error:', error);
    rootElement.innerHTML = `<div style="color: red; padding: 20px; background: yellow;">
      Minimal Router Error: ${error}
    </div>`;
  }
}
