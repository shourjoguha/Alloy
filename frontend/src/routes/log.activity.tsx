import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ArrowLeft, Save } from 'lucide-react';
import { useActivityDefinitions, useLogActivity } from '@/api/logs';
import { Spinner } from '@/components/common/Spinner';

export const Route = createFileRoute('/log/activity')({
  component: LogActivityPage,
});

const activitySchema = z.object({
  activity_definition_id: z.coerce.number().min(1, "Please select an activity"),
  activity_name: z.string().max(50, "Max 50 characters").optional(),
  duration_minutes: z.coerce.number().min(1, "Duration must be at least 1 minute"),
  distance_km: z.coerce.number().min(0, "Distance must be positive").optional(),
  notes: z.string().max(500, "Max 500 characters").optional(),
  perceived_difficulty: z.coerce.number().min(1).max(10),
  enjoyment_rating: z.coerce.number().min(1).max(5),
});

type ActivityFormValues = z.infer<typeof activitySchema>;

function LogActivityPage() {
  const navigate = useNavigate();
  const { data: activities, isLoading: isLoadingActivities } = useActivityDefinitions();
  const { mutate: logActivity, isPending: isSubmitting } = useLogActivity();

  const form = useForm({
    resolver: zodResolver(activitySchema),
    defaultValues: {
      perceived_difficulty: 5,
      enjoyment_rating: 3,
      duration_minutes: 30,
      distance_km: 0,
      activity_definition_id: 0,
    },
  });

  const selectedActivityId = Number(useWatch({ control: form.control, name: 'activity_definition_id' }));
  const selectedActivity = activities?.find(a => a.id === selectedActivityId);
  const perceivedDifficulty = useWatch({ control: form.control, name: 'perceived_difficulty' });
  const enjoymentRating = useWatch({ control: form.control, name: 'enjoyment_rating' });
  const notes = useWatch({ control: form.control, name: 'notes' });
  // Check for 'cardio' (lowercase from enum) or 'CARDIO' (just in case)
  const isCardio = selectedActivity?.category?.toLowerCase() === 'cardio';

  const onSubmit = (data: ActivityFormValues) => {
    logActivity({
      ...data,
      distance_km: isCardio && data.distance_km && data.distance_km > 0 ? data.distance_km : undefined,
    }, {
      onSuccess: () => {
        navigate({ to: '/' });
      },
    });
  };

  if (isLoadingActivities) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="container-app py-6 space-y-6 animate-fade-in">
      <div className="flex items-center space-x-4">
        <Button variant="ghost" size="icon" onClick={() => window.history.back()}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <h1 className="text-xl font-semibold">Log Activity</h1>
      </div>

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <Card className="p-6 space-y-6">
          {/* Activity Selector */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Activity</label>
            <div className="space-y-3">
              <select
                {...form.register('activity_definition_id')}
                className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              >
                <option value="0">Select activity...</option>
                {activities?.map((activity) => (
                  <option key={activity.id} value={activity.id}>
                    {activity.name}
                  </option>
                ))}
              </select>
              
              <input
                type="text"
                {...form.register('activity_name')}
                placeholder="Name your activity (optional)"
                maxLength={50}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              />
            </div>
            {form.formState.errors.activity_definition_id && (
              <p className="text-sm text-destructive">{form.formState.errors.activity_definition_id.message}</p>
            )}
          </div>

          {/* Duration */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Duration (minutes)</label>
            <input
              type="number"
              {...form.register('duration_minutes')}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            />
            {form.formState.errors.duration_minutes && (
              <p className="text-sm text-destructive">{form.formState.errors.duration_minutes.message}</p>
            )}
          </div>

          {/* Distance (Conditional for Cardio) */}
          {isCardio && (
            <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
              <label className="text-sm font-medium">Distance (km)</label>
              <input
                type="number"
                step="0.01"
                {...form.register('distance_km')}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              />
              {form.formState.errors.distance_km && (
                <p className="text-sm text-destructive">{form.formState.errors.distance_km.message}</p>
              )}
            </div>
          )}

          {/* Difficulty */}
          <div className="space-y-2">
            <label className="text-sm font-medium flex justify-between">
              <span>Perceived Difficulty (1-10)</span>
              <span className="text-foreground-muted font-normal">{String(perceivedDifficulty)}</span>
            </label>
            <input
              type="range"
              min="1"
              max="10"
              step="1"
              {...form.register('perceived_difficulty')}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-foreground-muted">
              <span>Very Easy</span>
              <span>Max Effort</span>
            </div>
          </div>

          {/* Enjoyment */}
          <div className="space-y-2">
            <label className="text-sm font-medium flex justify-between">
              <span>Enjoyment Rating (1-5)</span>
              <span className="text-foreground-muted font-normal">{String(enjoymentRating)}</span>
            </label>
            <input
              type="range"
              min="1"
              max="5"
              step="1"
              {...form.register('enjoyment_rating')}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-foreground-muted">
              <span>Hated it</span>
              <span>Loved it</span>
            </div>
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Notes</label>
            <textarea
              {...form.register('notes')}
              className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              placeholder="How did it feel?"
            />
            <p className="text-xs text-foreground-muted text-right">
              {notes?.length || 0}/500
            </p>
            {form.formState.errors.notes && (
              <p className="text-sm text-destructive">{form.formState.errors.notes.message}</p>
            )}
          </div>
        </Card>

        <div className="flex gap-4">
          <Button
            type="button"
            variant="outline"
            className="flex-1"
            onClick={() => window.history.back()}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            className="flex-1"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <Spinner className="mr-2 h-4 w-4" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Log Activity
          </Button>
        </div>
      </form>
    </div>
  );
}
