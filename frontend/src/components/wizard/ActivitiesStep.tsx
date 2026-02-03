import { useState } from 'react';
import { useProgramWizardStore } from '@/stores/program-wizard-store';
import { cn } from '@/lib/utils';
import { Plus, X } from 'lucide-react';

const ACTIVITY_CATEGORIES = [
  {
    category: 'sports',
    name: 'Sports',
    activities: [
      { type: 'basketball', name: 'Basketball', icon: '🏀' },
      { type: 'soccer', name: 'Soccer', icon: '⚽' },
      { type: 'tennis', name: 'Tennis', icon: '🎾' },
      { type: 'golf', name: 'Golf', icon: '⛳' },
      { type: 'swimming', name: 'Swimming', icon: '🏊' },
      { type: 'martial_arts', name: 'Martial Arts', icon: '🥋' },
    ],
  },
  {
    category: 'cardio',
    name: 'Cardio',
    activities: [
      { type: 'running', name: 'Running', icon: '🏃' },
      { type: 'cycling', name: 'Cycling', icon: '🚴' },
      { type: 'rowing', name: 'Rowing', icon: '🚣' },
      { type: 'hiking', name: 'Hiking', icon: '🥾' },
      { type: 'jump_rope', name: 'Jump Rope', icon: '⏱️' },
    ],
  },
  {
    category: 'recovery',
    name: 'Recovery',
    activities: [
      { type: 'yoga', name: 'Yoga', icon: '🧘' },
      { type: 'stretching', name: 'Stretching', icon: '🤸' },
      { type: 'walking', name: 'Walking', icon: '🚶' },
      { type: 'foam_rolling', name: 'Foam Rolling', icon: '🛢️' },
      { type: 'sauna', name: 'Sauna', icon: '🧖' },
    ],
  },
] as const;

export function ActivitiesStep() {
  const { enjoyableActivities, addEnjoyableActivity, removeEnjoyableActivity } = useProgramWizardStore();
  const [customActivity, setCustomActivity] = useState('');

  const isSelected = (activityType: string) => {
    return enjoyableActivities.some((a) => a.activity_type === activityType);
  };

  const toggleActivity = (activityType: string) => {
    if (isSelected(activityType)) {
      removeEnjoyableActivity(activityType);
    } else {
      addEnjoyableActivity({ activity_type: activityType });
    }
  };

  const addCustomActivity = () => {
    if (customActivity.trim()) {
      addEnjoyableActivity({
        activity_type: 'custom',
        custom_name: customActivity.trim(),
      });
      setCustomActivity('');
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h2 className="text-xl font-bold">What do you enjoy?</h2>
        <p className="text-foreground-muted text-sm">
          Tell Jerome about activities you enjoy. He'll suggest these on rest days and work around your schedule.
        </p>
      </div>

      {/* Selected activities */}
      {enjoyableActivities.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {enjoyableActivities.map((activity) => (
            <span
              key={activity.activity_type + (activity.custom_name || '')}
              className="inline-flex items-center gap-1 text-sm px-3 py-1.5 rounded-full bg-primary/10 text-primary"
            >
              {activity.custom_name || activity.activity_type}
              <button
                onClick={() => removeEnjoyableActivity(activity.activity_type)}
                className="hover:bg-primary/20 rounded-full p-0.5"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Activity categories */}
      {ACTIVITY_CATEGORIES.map((category) => (
        <div key={category.category} className="space-y-3">
          <h3 className="text-sm font-medium text-foreground-muted">{category.name}</h3>
          <div className="flex flex-wrap gap-2">
            {category.activities.map((activity) => (
              <button
                key={activity.type}
                onClick={() => toggleActivity(activity.type)}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all",
                  isSelected(activity.type)
                    ? "bg-primary text-white"
                    : "bg-background-input hover:bg-background-secondary text-foreground"
                )}
              >
                <span>{activity.icon}</span>
                <span>{activity.name}</span>
              </button>
            ))}
          </div>
        </div>
      ))}

      {/* Custom activity */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-foreground-muted">Something else?</h3>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Add custom activity..."
            value={customActivity}
            onChange={(e) => setCustomActivity(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addCustomActivity()}
            className="flex-1 h-10 px-4 rounded-lg bg-background-input border-0 focus:outline-none focus:ring-2 focus:ring-primary text-sm"
          />
          <button
            onClick={addCustomActivity}
            disabled={!customActivity.trim()}
            className={cn(
              "h-10 w-10 rounded-lg flex items-center justify-center transition-colors",
              customActivity.trim()
                ? "bg-primary text-white"
                : "bg-background-input text-foreground-subtle cursor-not-allowed"
            )}
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
      </div>

      <p className="text-center text-xs text-foreground-subtle">
        💡 This is optional. It helps Jerome plan recovery and avoid scheduling conflicts.
      </p>
    </div>
  );
}
