// Absolute minimal test
const rootEl = document.getElementById('root');

if (rootEl) {
  rootEl.innerHTML = '<div style="color: white; padding: 50px; font-size: 32px; font-weight: bold;">TEST - HTML Direct Injection Working!</div>';
} else {
  console.error('Root element not found');
}
