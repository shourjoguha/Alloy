import { createRoot } from 'react-dom/client';
import { RouterProvider, createRouter } from '@tanstack/react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { routeTree } from './routeTree.gen';

console.log('=== Router Test Step 2: Importing routeTree ===');
console.log('routeTree:', routeTree);

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

console.log('=== Router Test Step 2: Creating router ===');

const router = createRouter({
  routeTree,
  context: {
    queryClient,
  },
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
});

console.log('=== Router Test Step 2: Router created ===');
console.log('Router state:', router.state);

const rootElement = document.getElementById('root');
console.log('=== Router Test Step 2: Root element:', rootElement);

if (rootElement) {
  try {
    const root = createRoot(rootElement);
    console.log('=== Router Test Step 2: Root created ===');

    console.log('=== Router Test Step 2: Starting render ===');
    root.render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    );
    console.log('=== Router Test Step 2: Render complete ===');
  } catch (error) {
    console.error('=== Router Test Step 2: Render error:', error);
    rootElement.innerHTML = `<div style="color: red; padding: 50px; background: yellow; font-size: 24px;">
      Router Render Error: ${error}
    </div>`;
  }
}
