import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

console.log('=== Router Test Step 1: Testing basic React ===');

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

const rootElement = document.getElementById('root');

if (rootElement) {
  const root = createRoot(rootElement);
  root.render(
    <QueryClientProvider client={queryClient}>
      <div style={{
        color: 'white',
        padding: '50px',
        fontSize: '32px',
        fontWeight: 'bold',
        backgroundColor: 'blue'
      }}>
        ROUTER TEST STEP 1 - React Working!
      </div>
    </QueryClientProvider>
  );
  console.log('=== Router Test Step 1: Render complete ===');
}
