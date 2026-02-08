console.log('=== STEP 3: File is executing ===');

document.addEventListener('DOMContentLoaded', () => {
  console.log('=== STEP 3: DOMContentLoaded ===');
  const root = document.getElementById('root');
  if (root) {
    root.innerHTML = 'STEP 3: JavaScript is running!';
    console.log('=== STEP 3: Content added to root ===');
  }
});
