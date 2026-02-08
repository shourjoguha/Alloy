import { createRoot } from 'react-dom/client';
import { RouterProvider, createRouter } from '@tanstack/react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { routeTree } from './routeTree.gen';
import '@/styles/globals.css';

console.log('Starting app initialization...');

// Create query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      gcTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

console.log('Query client created');

// Create router instance
const router = createRouter({
  routeTree,
  context: {
    queryClient,
  },
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
});

console.log('Router created:', router);

// Register router type for type safety
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

console.log('Creating root and rendering...');

try {
  createRoot(document.getElementById('root')!).render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      {import.meta.env.DEV && <ReactQueryDevtools buttonPosition="bottom-left" />}
    </QueryClientProvider>
  );
  console.log('Render complete');
} catch (error) {
  console.error('Render error:', error);
  document.getElementById('root')!.innerHTML = `<div style="color: red; padding: 20px;">Render Error: ${error}</div>`;
}
