# Circuit Display Integration Guide

This guide shows how to integrate the new CircuitDisplay component with the existing SessionCard component in the Gainsly application.

## Current State

The existing `SessionCard.tsx` component has a basic `CircuitDisplay` function (lines 110-185) that displays circuit information in a simple format.

## Integration Steps

### Step 1: Import the New Component

In `/Users/shourjosmac/Documents/alloy/frontend/src/components/program/SessionCard.tsx`, replace the existing import section:

```tsx
// Remove this import (no longer needed):
// import { Clock, Flame, Coffee, Dumbbell } from 'lucide-react';

// Keep these imports:
import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { ChevronDown, ChevronUp, Clock, Flame, Coffee } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Session, ExerciseBlock, CircuitExercise } from '@/types';

// Add this new import:
import { CircuitDisplay, CircuitDisplayCompact } from '@/components/circuit';
```

### Step 2: Remove Old Circuit Display Function

Delete the existing `CircuitDisplay` function (lines 110-185 in the current file). This function is replaced by the new component.

```tsx
// DELETE these lines (110-185):
function CircuitDisplay({ circuit, title = "Circuit Block" }: { circuit: any; title?: string }) {
  // ... old implementation
}
```

### Step 3: Update Circuit Type Configuration (Optional)

You can keep the existing `SESSION_TYPE_CONFIG` for session types, but remove the old `formatCircuitExercise` function if it's only used by the old CircuitDisplay.

### Step 4: Replace CircuitDisplay Calls

In the SessionCard component's render section, replace the old CircuitDisplay function calls:

**Before:**
```tsx
// Line 287
<CircuitDisplay circuit={session.circuit} title="Circuit Block" />

// Lines 291-292
{session.finisher_circuit ? (
  <CircuitDisplay circuit={session.finisher_circuit} title="Finisher" />
) : session.finisher && (
  // ... finisher display logic
)}
```

**After:**
```tsx
// Main circuit block
<CircuitDisplay circuit={session.circuit} title="Circuit Block" />

// Finisher circuit
{session.finisher_circuit ? (
  <CircuitDisplay circuit={session.finisher_circuit} title="Finisher" />
) : session.finisher && (
  // Keep existing finisher display for non-circuit finishers
  <div className="mt-3">
    <h4 className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-2 flex items-center gap-1">
      <Flame className="h-3 w-3 text-orange-500" />
      Finisher
    </h4>
    {/* ... existing finisher display code */}
  </div>
)}
```

### Step 5: Update Finisher Display (Optional Enhancement)

For consistency, you might want to enhance the non-circuit finisher display. Here's an improved version:

```tsx
{session.finisher_circuit ? (
  <CircuitDisplay circuit={session.finisher_circuit} title="Finisher" />
) : session.finisher && (
  <div className="mt-3">
    <h4 className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-2 flex items-center gap-1">
      <Flame className="h-3 w-3 text-orange-500" />
      Finisher
    </h4>
    <div className="p-3 bg-background-input rounded-lg border border-border/30">
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-foreground">
          {session.finisher.type || 'Finisher'}
        </span>
        <div className="flex items-center gap-2">
          {session.finisher.circuit_type && (
            <span className="text-xs text-primary bg-primary/10 px-2 py-0.5 rounded font-medium">
              {session.finisher.circuit_type}
            </span>
          )}
          {session.finisher.duration_minutes && (
            <span className="text-xs text-foreground-muted bg-background-input px-2 py-0.5 rounded">
              {session.finisher.duration_minutes} min
            </span>
          )}
          {session.finisher.rounds && (
            <span className="text-xs text-foreground-muted bg-background-input px-2 py-0.5 rounded">
              {session.finisher.rounds}
            </span>
          )}
        </div>
      </div>
      
      {session.finisher.exercises && session.finisher.exercises.length > 0 && (
        <div className="border-t border-border/50 pt-2">
          <div className="text-xs text-foreground-muted mb-2">Exercises:</div>
          <div className="space-y-1">
            {session.finisher.exercises.map((ex, idx) => (
              <div key={idx} className="flex items-center justify-between text-sm">
                <div className="flex-1">
                  <span className="text-foreground font-medium">
                    {ex.movement}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-foreground-muted">
                  {ex.reps && (
                    <span className="bg-background-input px-2 py-0.5 rounded">
                      {ex.reps} reps
                    </span>
                  )}
                  {ex.duration_seconds && (
                    <span className="bg-background-input px-2 py-0.5 rounded">
                      {ex.duration_seconds}s
                    </span>
                  )}
                  {ex.rep_range_min && ex.rep_range_max && (
                    <span className="bg-background-input px-2 py-0.5 rounded">
                      {ex.rep_range_min}-{ex.rep_range_max}
                    </span>
                  )}
                  {ex.rest_seconds && (
                    <span className="text-foreground-muted/60">
                      rest {ex.rest_seconds}s
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  </div>
)}
```

## Complete Integration Example

Here's the complete updated SessionCard component with the new CircuitDisplay integrated:

```tsx
import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { ChevronDown, ChevronUp, Clock, Flame, Coffee } from 'lucide-react';
import { cn } from '@/lib/utils';
import { CircuitDisplay } from '@/components/circuit';
import type { Session, ExerciseBlock } from '@/types';

interface SessionCardProps {
  session: Session;
  defaultExpanded?: boolean;
}

// Session type display config (unchanged)
const SESSION_TYPE_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  upper: { label: 'Upper Body', icon: '💪', color: 'bg-blue-500' },
  lower: { label: 'Lower Body', icon: '🦵', color: 'bg-green-500' },
  push: { label: 'Push', icon: '🏋️', color: 'bg-red-500' },
  pull: { label: 'Pull', icon: '🧲', color: 'bg-purple-500' },
  legs: { label: 'Legs', icon: '🦵', color: 'bg-green-500' },
  full_body: { label: 'Full Body', icon: '⚡', color: 'bg-yellow-500' },
  cardio: { label: 'Cardio', icon: '❤️', color: 'bg-pink-500' },
  mobility: { label: 'Mobility', icon: '🧘', color: 'bg-teal-500' },
  recovery: { label: 'Rest Day', icon: '😴', color: 'bg-gray-500' },
  skill: { label: 'Skill', icon: '🎯', color: 'bg-orange-500' },
  custom: { label: 'Custom', icon: '⚙️', color: 'bg-gray-500' },
};

// Helper functions (unchanged)
function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function ExerciseList({ exercises, title }: { exercises: ExerciseBlock[] | null | undefined; title: string }) {
  if (!exercises || exercises.length === 0) return null;

  return (
    <div className="mt-3">
      <h4 className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-2">
        {title}
      </h4>
      <div className="space-y-1.5">
        {exercises.map((exercise, idx) => (
          <div key={idx} className="flex items-center justify-between text-sm">
            <span className="text-foreground">{exercise.movement}</span>
            <span className="text-foreground-muted text-xs">
              {exercise.sets && (
                <>
                  {exercise.sets}×
                  {exercise.rep_range_min && exercise.rep_range_max
                    ? `${exercise.rep_range_min}-${exercise.rep_range_max}`
                    : exercise.duration_seconds
                    ? `${exercise.duration_seconds}s`
                    : '—'}
                </>
              )}
              {exercise.target_rpe && (
                <span className="ml-1 text-primary">@{exercise.target_rpe}</span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SessionCard({ session, defaultExpanded = false }: SessionCardProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [notesExpanded, setNotesExpanded] = useState(false);
  
  const config = SESSION_TYPE_CONFIG[session.session_type] || SESSION_TYPE_CONFIG.custom;
  const hasContent = session.main && session.main.length > 0;
  const isRestDay = session.session_type === 'recovery';
  const isGenerating = !isRestDay && !hasContent;
  const hasCoachNotes = session.coach_notes && session.coach_notes.length > 0;
  const hasCircuit = session.circuit !== undefined && session.circuit !== null;
  const hasFinisherCircuit = session.finisher_circuit !== undefined && session.finisher_circuit !== null;
  const hasAccessories = session.accessory && session.accessory.length > 0;

  return (
    <Card variant="grouped"
      className={cn(
        "overflow-hidden transition-all",
        isRestDay && "opacity-60"
      )}
    >
      {/* Header - always visible */}
      <button
        onClick={() => hasContent && setIsExpanded(!isExpanded)}
        className={cn(
          "w-full p-4 flex items-center gap-3 text-left",
          hasContent && "cursor-pointer hover:bg-background-secondary"
        )}
        disabled={!hasContent}
      >
        {/* Day indicator */}
        <div className={cn(
          "w-10 h-10 rounded-lg flex items-center justify-center text-lg",
          config.color,
          "bg-opacity-20"
        )}>
          {config.icon}
        </div>

        {/* Session info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium">{config.label}</span>
            {isRestDay && <Coffee className="h-3 w-3 text-foreground-muted" />}
            {isGenerating && (
              <span className="text-xs text-foreground-muted">Generating…</span>
            )}
          </div>
          <div className="text-xs text-foreground-muted flex items-center gap-2">
            <span>Day {session.day_number}</span>
            {session.session_date && (
              <>
                <span>•</span>
                <span>{formatDate(session.session_date)}</span>
              </>
            )}
          </div>
        </div>

        {/* Duration & expand */}
        <div className="flex items-center gap-2">
          {session.estimated_duration_minutes && (
            <div className="flex items-center gap-1 text-xs text-foreground-muted">
              <Clock className="h-3 w-3" />
              <span>{session.estimated_duration_minutes}m</span>
            </div>
          )}
          {hasContent && (
            <div className="text-foreground-muted">
              {isExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </div>
          )}
        </div>
      </button>

      {/* Expanded content */}
      {isExpanded && hasContent && (
        <div className="px-4 pb-4 border-t border-border/50">
          {/* Intent tags */}
          {session.intent_tags && session.intent_tags.length > 0 && (
            <div className="flex gap-1 flex-wrap mt-3">
              {session.intent_tags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-2 py-0.5 bg-background-input rounded text-foreground-muted"
                >
                  {tag.replace('_', ' ')}
                </span>
              ))}
            </div>
          )}

          {/* Exercise sections */}
          <ExerciseList exercises={session.warmup} title="Warmup" />
          <ExerciseList exercises={session.main} title="Main" />
          
          {/* Circuit or Accessory (mutually exclusive) */}
          <CircuitDisplay circuit={session.circuit} title="Circuit Block" />
          {!hasCircuit && <ExerciseList exercises={session.accessory} title="Accessory" />}
          
          {/* Finisher */}
          {session.finisher_circuit ? (
            <CircuitDisplay circuit={session.finisher_circuit} title="Finisher" />
          ) : session.finisher && (
            <div className="mt-3">
              <h4 className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-2 flex items-center gap-1">
                <Flame className="h-3 w-3 text-orange-500" />
                Finisher
              </h4>
              {/* ... enhanced finisher display code from Step 5 ... */}
            </div>
          )}

          <ExerciseList exercises={session.cooldown} title="Cooldown" />

          {/* Coach notes */}
          {hasCoachNotes && session.coach_notes && (
            <div className="mt-3 p-2 bg-background-input rounded text-xs text-foreground-muted">
              <div className="flex items-start justify-between">
                <span className="font-medium">Jerome's Notes:</span>
              </div>
              <div className={cn(
                "mt-1",
                !notesExpanded && "line-clamp-3"
              )}>
                {session.coach_notes}
              </div>
              {session.coach_notes.length > 150 && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setNotesExpanded(!notesExpanded);
                  }}
                  className="mt-2 flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
                >
                  {notesExpanded ? 'Show less' : 'See more'}
                  {notesExpanded ? (
                    <ChevronUp className="h-3 w-3" />
                  ) : (
                    <ChevronDown className="h-3 w-3" />
                  )}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
```

## Testing

After integration, test the following scenarios:

1. **AMRAP Circuit**: Verify proper display with time cap and max rounds indicator
2. **EMOM Circuit**: Check work/rest interval display
3. **RFT Circuit**: Ensure round count is shown correctly
4. **Ladder Circuit**: Verify ladder notes display
5. **Distance-based exercises**: Check proper unit formatting (meters/kilometers)
6. **Calorie-based exercises**: Verify calorie display with "Max Cals" tag
7. **Time-based exercises**: Check proper time formatting (seconds/minutes)
8. **Prescribed weights**: Ensure male/female weights display correctly
9. **Rest between exercises**: Verify rest seconds display
10. **Muscle tags**: Check that primary muscles are shown as tags

## Benefits of Integration

1. **Visual Distinction**: Circuits are immediately recognizable with color-coded headers and badges
2. **Better Information Hierarchy**: Circuit metrics are prominent, exercise details are clear
3. **Improved Scanning**: Color-coded metrics allow quick visual scanning
4. **Consistent Styling**: Aligns with Gainsly design system
5. **Accessibility**: High contrast ratios and semantic HTML
6. **Responsive**: Works well on mobile and desktop
7. **Extensible**: Easy to add new circuit types or modify styling

## Troubleshooting

### Circuit Not Displaying

If circuits don't display:
- Check that `circuit` prop is not null/undefined
- Verify `circuit.exercises` array exists and has items
- Ensure `CircuitBlock` type matches expected structure

### Styling Issues

If styling looks off:
- Ensure Tailwind CSS classes are properly configured
- Check that globals.css is imported
- Verify design token variables are defined

### TypeScript Errors

If TypeScript errors occur:
- Ensure CircuitBlock type is imported from '@/types'
- Check that all required properties are present
- Verify no type mismatches in props

## Future Enhancements

After integration, consider adding:

1. **Compact Mode**: Use `CircuitDisplayCompact` for list views or dashboards
2. **Interactive Timer**: Add countdown timer functionality for live workouts
3. **Progress Tracking**: Show completion status for each exercise
4. **Animation**: Add subtle animations for exercise completion
5. **Dark Mode**: Extend component to support dark theme
6. **Custom Circuit Types**: Add support for custom circuit types beyond the standard ones
