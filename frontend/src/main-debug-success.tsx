// Add a script that executes immediately
(function() {
  console.log('=== DEBUG: Immediate execution test ===');
  window.__DEBUG_LOADED__ = true;
  
  const root = document.getElementById('root');
  if (root) {
    console.log('=== DEBUG: Root element found ===');
    root.innerHTML = '<div style="color: white; padding: 20px; background: red; font-size: 24px;">DEBUG - Immediate execution worked!</div>';
    console.log('=== DEBUG: Root updated ===');
  } else {
    console.error('=== DEBUG: Root element NOT found ===');
  }
  
  console.log('=== DEBUG: Test complete ===');
})();
