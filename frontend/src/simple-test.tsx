import { createRoot } from 'react-dom/client';

const rootElement = document.getElementById('root');
if (rootElement) {
  const root = createRoot(rootElement);
  root.render(
    <div style={{color: 'white', padding: '50px', fontSize: '32px', fontWeight: 'bold', backgroundColor: 'blue'}}>
      SIMPLE TEST - REACT WORKS!
    </div>
  );
}
