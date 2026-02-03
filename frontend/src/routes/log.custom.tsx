import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { Card } from '@/components/ui/card';
import { Dumbbell, Activity, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

export const Route = createFileRoute('/log/custom')({
  component: LogCustomPage,
});

function LogCustomPage() {
  const navigate = useNavigate();

  return (
    <div className="container-app py-6 space-y-6 animate-fade-in">
      <div className="flex items-center space-x-4">
        <Button variant="ghost" size="icon" onClick={() => window.history.back()}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <h1 className="text-xl font-semibold">Log Custom Workout</h1>
      </div>

      <div className="grid grid-cols-1 gap-4">
        <Card 
          className="p-6 flex items-center justify-between cursor-pointer hover:bg-background-elevated transition-colors"
          onClick={() => navigate({ to: '/log/activity' })}
        >
          <div className="flex items-center space-x-4">
            <div className="p-3 bg-primary/10 rounded-full text-primary">
              <Activity className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Activity</h3>
              <p className="text-sm text-foreground-muted">Log a generic activity (Running, Yoga, etc.)</p>
            </div>
          </div>
        </Card>

        <Card 
          className="p-6 flex items-center justify-between cursor-pointer hover:bg-background-elevated transition-colors"
          onClick={() => navigate({ to: '/log/workout' })}
        >
          <div className="flex items-center space-x-4">
            <div className="p-3 bg-secondary/10 rounded-full text-secondary">
              <Dumbbell className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Workout</h3>
              <p className="text-sm text-foreground-muted">Log a custom strength training session</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
