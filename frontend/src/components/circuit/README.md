# Circuit Display Component

A specialized React component for displaying circuit workouts with proper visual hierarchy, metric color-coding, and circuit type distinction.

## Overview

The CircuitDisplay component is designed to clearly differentiate circuit workouts from regular exercise blocks in the Gainsly application. It provides visual distinction through color-coding, iconography, and structured layouts that make circuit workouts immediately recognizable.

## Features

### Circuit Type Differentiation

Each circuit type (AMRAP, EMOM, RFT, LADDER, CHIPPER, TABATA, STATION) has distinct styling:

- **AMRAP** (Amber): As Many Rounds As Possible - warm, energetic feel
- **EMOM** (Blue): Every Minute On the Minute - consistent, rhythmic feel
- **RFT** (Green): Rounds For Time - progressive, growth-oriented feel
- **LADDER** (Purple): Ascending/Descending Reps - mysterious, challenging feel
- **CHIPPER** (Orange): Complete in Order - intense, fiery feel
- **TABATA** (Rose): High-intensity intervals - urgent, intense feel
- **STATION** (Teal): Station-based circuit - structured, calm feel

### Metric Color-Coding

Exercise metrics are color-coded for quick visual scanning:

- **Reps** (Blue): `bg-blue-50`, `text-blue-700`
- **Time** (Amber): `bg-amber-50`, `text-amber-700`
- **Distance** (Green): `bg-green-50`, `text-green-700`
- **Calories** (Orange): `bg-orange-50`, `text-orange-700`

### Circuit-Level Metrics

Display prominently at the top of the circuit:

- **Time Cap**: Shows total duration (e.g., "16 min", "7 min")
- **Rounds**: Number of rounds for RFT circuits (e.g., "3 rounds", "5 rounds")
- **Work/Rest Intervals**: For EMOM circuits (e.g., "40s work / 20s rest")
- **Duration**: Estimated workout time in footer

### Exercise Information

Each exercise displays:

- Sequential numbering with metric-type coloring
- Movement name
- Primary metric (single value, not range):
  - Reps: "5 reps", "10 reps"
  - Time: "30 seconds", "2 minutes"
  - Distance: "100 meters", "1 km"
  - Calories: "20 cal"
- Prescribed weights (male/female) when available
- Rest seconds between exercises if specified
- Max effort indicators for special cases

## Components

### CircuitDisplay

The main full-sized circuit display component.

```tsx
import { CircuitDisplay } from '@/components/circuit';

<CircuitDisplay 
  circuit={circuitData} 
  title="Circuit Block"
  showMetrics={true}
/>
```

**Props:**

- `circuit` (required): CircuitBlock object
- `title` (optional, default: "Circuit Block"): Section header text
- `showMetrics` (optional, default: true): Show/hide circuit-level metrics

### CircuitDisplayCompact

A compact version for use in lists, cards, or tight spaces.

```tsx
import { CircuitDisplayCompact } from '@/components/circuit';

<CircuitDisplayCompact circuit={circuitData} />
```

**Props:**

- `circuit` (required): CircuitBlock object

## Data Structure

The component expects a `CircuitBlock` object with the following structure:

```typescript
interface CircuitBlock {
  circuit_id: number;
  name: string;
  circuit_type: string; // 'AMRAP', 'EMOM', 'RFT', 'LADDER', etc.
  difficulty_tier: number;
  estimated_duration_seconds: number;
  default_rounds: number;
  primary_region: string;
  primary_muscles: string[];
  fatigue_factor: number;
  stimulus_factor: number;
  exercises: CircuitExercise[];
}

interface CircuitExercise {
  movement: string;
  movement_id: number;
  sequence: number;
  metric_type: string; // 'reps', 'time', 'distance', 'calories'
  reps?: number;
  distance_meters?: number;
  duration_seconds?: number;
  calories?: number;
  rest_seconds?: number;
  notes?: string;
  rx_weight_male?: number;
  rx_weight_female?: number;
}
```

## Integration with SessionCard

Replace the existing `CircuitDisplay` function in `SessionCard.tsx` with the new component:

```tsx
import { CircuitDisplay, CircuitDisplayCompact } from '@/components/circuit';

// In SessionCard component:
<CircuitDisplay circuit={session.circuit} title="Circuit Block" />
<CircuitDisplay circuit={session.finisher_circuit} title="Finisher" />
```

## Design Principles

### Visual Hierarchy

1. **Circuit Type**: Most prominent, uses color badges and icons
2. **Circuit Name**: Bold, large text in header
3. **Circuit Metrics**: Secondary information, pill badges
4. **Exercise List**: Structured, numbered, easy to scan
5. **Exercise Details**: Smaller text, secondary emphasis

### Accessibility

- High contrast ratios (4.5:1 minimum) for text
- Semantic HTML structure
- Keyboard navigable
- Focus indicators for interactive elements
- Color coding supplemented with icons and text

### Responsive Design

- Mobile-first approach
- Adjusts spacing and font sizes for smaller screens
- Maintains readability across device sizes
- Touch-friendly hit targets (minimum 44px)

### Performance

- Minimal re-renders through proper React patterns
- CSS transitions instead of JavaScript animations
- Optimized for list rendering with circuit data

## Customization

### Adding New Circuit Types

To add a new circuit type, update the `CIRCUIT_TYPE_CONFIG` object:

```typescript
const CIRCUIT_TYPE_CONFIG: Record<string, { ... }> = {
  // ... existing types
  NEW_TYPE: {
    label: 'New Type',
    icon: NewIcon,
    color: 'bg-indigo-500',
    bgColor: 'bg-indigo-50',
    textColor: 'text-indigo-700',
    description: 'Description of this circuit type'
  }
};
```

### Modifying Metric Colors

To change metric color schemes, update the `METRIC_COLORS` object:

```typescript
const METRIC_COLORS: Record<string, { ... }> = {
  reps: {
    color: 'blue',
    bgColor: 'bg-blue-50',
    textColor: 'text-blue-700',
    icon: Target
  },
  // ... other metrics
};
```

## Styling

The component uses Tailwind CSS classes that align with the Gainsly design system:

- Colors: iOS light theme palette
- Typography: iOS font stack (Avenir Next, SF Pro)
- Spacing: Consistent spacing units
- Border radius: 8-12px range
- Shadows: Subtle, layered approach

### Custom CSS

Additional styles are provided in `CircuitDisplay.css` for:

- Circuit type-specific header backgrounds
- Metric badge hover effects
- Exercise row animations
- Compact display styling
- Responsive adjustments
- Print styles

## Examples

See `CircuitDisplayExample.tsx` for comprehensive examples of all circuit types and their variations.

### AMRAP Example

```
The Filthy Fifty (AMRAP)
├── Time Cap: 16 min
├── Rounds: Max rounds
└── Exercises:
    1. Box Jumps - 50 reps [♂24kg ♀20kg]
    2. Jumping Pull-ups - 50 reps
    3. Kettlebell Swings - 50 reps [♂24kg ♀16kg]
    4. Walking Lunges - 50 reps
    5. Knees to Elbows - 50 reps
```

### EMOM Example

```
Power Hour (EMOM)
├── Time Cap: 8 min
├── Work/Rest: 60s work / 0s rest
└── Exercises:
    1. Burpees - 10 reps (Minute 1)
    2. Power Cleans - 5 reps [♂61kg ♀43kg] (Minute 2)
```

### RFT Example

```
The Chief (RFT)
├── Time Cap: 10 min
├── Rounds: 5 rounds
└── Exercises:
    1. Power Cleans - 3 reps [♂84kg ♀57kg] (Rest: 60s)
    2. Push-ups - 6 reps (Rest: 60s)
    3. Air Squats - 9 reps
```

## Browser Support

- Chrome/Edge: Latest 2 versions
- Firefox: Latest 2 versions
- Safari: Latest 2 versions
- iOS Safari: iOS 14+
- Android Chrome: Latest version

## Future Enhancements

Potential improvements for future iterations:

- Dark mode support
- Animation for round completion
- Interactive timer for live workouts
- Progress tracking visualization
- Circuit comparison mode
- Export to PDF/image
- Voice control integration
- Metric unit conversion (imperial/metric)
