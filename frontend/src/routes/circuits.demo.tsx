import { createFileRoute } from '@tanstack/react-router';
import CircuitDisplayExample from '@/components/circuit/CircuitDisplayExample';

export const Route = createFileRoute('/circuits/demo')({
  component: CircuitDemo,
});

function CircuitDemo() {
  return (
    <div className="min-h-screen bg-background">
      <div className="container-app py-8">
        <CircuitDisplayExample />
      </div>
    </div>
  );
}
