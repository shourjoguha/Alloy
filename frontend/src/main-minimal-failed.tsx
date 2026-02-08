import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient();

console.log('Minimal app starting...');

const root = createRoot(document.getElementById('root')!);

root.render(
  <QueryClientProvider client={queryClient}>
    <div style={{ color: 'white', padding: '20px', fontSize: '24px' }}>
      Minimal Test - If you see this, React is working!
    </div>
  </QueryClientProvider>
);

console.log('Minimal app rendered');
