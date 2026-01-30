# Circuit Display Component - Design Summary

## Overview

A specialized React component system for displaying circuit workouts with proper visual hierarchy, metric color-coding, and circuit type distinction in the Gainsly application.

## Delivered Components

### 1. CircuitDisplay Component
**Location:** [`/Users/shourjosmac/Documents/alloy/frontend/src/components/circuit/CircuitDisplay.tsx`](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/circuit/CircuitDisplay.tsx)

A full-featured circuit display component with:
- Distinct circuit type styling (AMRAP, EMOM, RFT, LADDER, CHIPPER, TABATA, STATION)
- Color-coded metric badges (reps=blue, time=amber, distance=green, calories=orange)
- Circuit-level metrics display (time cap, rounds, work/rest intervals)
- Exercise list with sequential numbering
- Prescribed weights display (male/female)
- Rest seconds between exercises
- Max effort indicators

**Props:**
- `circuit` (required): CircuitBlock object
- `title` (optional, default: "Circuit Block"): Section header text
- `showMetrics` (optional, default: true): Show/hide circuit-level metrics

### 2. CircuitDisplayCompact Component
**Location:** Same file as CircuitDisplay

A compact version for use in lists, cards, or tight spaces.

**Props:**
- `circuit` (required): CircuitBlock object

### 3. Styling System
**Location:** [`/Users/shourjosmac/Documents/alloy/frontend/src/components/circuit/CircuitDisplay.css`](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/circuit/CircuitDisplay.css)

Comprehensive CSS styling with:
- Circuit type-specific header backgrounds
- Metric badge hover effects
- Exercise row animations
- Responsive design adjustments
- Accessibility features
- Print styles

### 4. Example Component
**Location:** [`/Users/shourjosmac/Documents/alloy/frontend/src/components/circuit/CircuitDisplayExample.tsx`](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/circuit/CircuitDisplayExample.tsx)

Complete example showcasing:
- AMRAP circuit with reps
- EMOM circuit with time intervals
- RFT circuit with prescribed weights
- LADDER circuit with notes
- Distance-based exercises
- Calorie-based exercises with max
- Compact display examples

### 5. Demo Route
**Location:** [`/Users/shourjosmac/Documents/alloy/frontend/src/routes/circuits.demo.tsx`](file:///Users/shourjosmac/Documents/alloy/frontend/src/routes/circuits.demo.tsx)

Demo page to view all circuit display examples.

**Access:** Visit `/circuits/demo` in your application

## Design Features

### Circuit Type Differentiation

Each circuit type has distinct styling:

| Type | Color | Header BG | Description |
|------|-------|-----------|-------------|
| AMRAP | Amber | bg-amber-50 | As Many Rounds As Possible |
| EMOM | Blue | bg-blue-50 | Every Minute On the Minute |
| RFT | Green | bg-green-50 | Rounds For Time |
| LADDER | Purple | bg-purple-50 | Ascending/Descending Reps |
| CHIPPER | Orange | bg-orange-50 | Complete in Order |
| TABATA | Rose | bg-rose-50 | High-intensity intervals |
| STATION | Teal | bg-teal-50 | Station-based circuit |

### Metric Color-Coding

| Metric Type | Color | Badge BG | Text Color |
|-------------|-------|----------|------------|
| Reps | Blue | bg-blue-50 | text-blue-700 |
| Time | Amber | bg-amber-50 | text-amber-700 |
| Distance | Green | bg-green-50 | text-green-700 |
| Calories | Orange | bg-orange-50 | text-orange-700 |

### Information Hierarchy

1. **Circuit Type** - Most prominent (color badge + icon)
2. **Circuit Name** - Bold, large text in header
3. **Circuit Metrics** - Secondary information (pill badges)
4. **Exercise List** - Structured, numbered, easy to scan
5. **Exercise Details** - Smaller text, secondary emphasis

## Integration

### Quick Integration

Replace existing `CircuitDisplay` function in `SessionCard.tsx`:

```tsx
// Add import
import { CircuitDisplay, CircuitDisplayCompact } from '@/components/circuit';

// Replace old CircuitDisplay calls
<CircuitDisplay circuit={session.circuit} title="Circuit Block" />
<CircuitDisplay circuit={session.finisher_circuit} title="Finisher" />
```

### Full Integration Guide

See [`INTEGRATION_GUIDE.md`](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/circuit/INTEGRATION_GUIDE.md) for:
- Step-by-step integration instructions
- Complete code examples
- Testing scenarios
- Troubleshooting tips

## Usage Examples

See [`USAGE_EXAMPLES.tsx`](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/circuit/USAGE_EXAMPLES.tsx) for:
- 15+ practical usage examples
- Different integration patterns
- Conditional rendering
- Loading and error states
- Responsive layouts

## Data Structure

The component expects a `CircuitBlock` object:

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

## Testing

### Test Data and Validation

See [`CircuitDisplay.test.tsx`](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/circuit/CircuitDisplay.test.tsx) for:
- Valid test circuits for all types
- Type validation functions
- Test runner for data validation

### Manual Testing Checklist

After integration, verify:
- [ ] AMRAP circuit displays with time cap
- [ ] EMOM circuit shows work/rest intervals
- [ ] RFT circuit displays round count
- [ ] LADDER circuit shows ladder notes
- [ ] Distance exercises format correctly (meters/km)
- [ ] Calorie exercises display "Max Cals" tag
- [ ] Time exercises format correctly (seconds/minutes)
- [ ] Prescribed weights show male/female values
- [ ] Rest seconds display between exercises
- [ ] Muscle tags display correctly
- [ ] Color coding is consistent
- [ ] Hover effects work properly
- [ ] Responsive design works on mobile

## Design System Alignment

The component integrates seamlessly with Gainsly design system:

- **Colors:** iOS light theme palette from `globals.css`
- **Typography:** iOS font stack (Avenir Next, SF Pro)
- **Spacing:** Consistent spacing units
- **Border radius:** 8-12px range (rounded-lg to rounded-xl)
- **Shadows:** Subtle, layered approach
- **Transitions:** Fast (150ms), Normal (200ms), Slow (300ms)

## Accessibility Features

- High contrast ratios (4.5:1 minimum)
- Semantic HTML structure
- Keyboard navigable
- Focus indicators for interactive elements
- Color coding supplemented with icons and text
- Proper ARIA labels where needed

## Browser Support

- Chrome/Edge: Latest 2 versions
- Firefox: Latest 2 versions
- Safari: Latest 2 versions
- iOS Safari: iOS 14+
- Android Chrome: Latest version

## File Structure

```
frontend/src/components/circuit/
├── CircuitDisplay.tsx          # Main component (CircuitDisplay + CircuitDisplayCompact)
├── CircuitDisplay.css           # Comprehensive styling
├── CircuitDisplayExample.tsx     # Example usage with test data
├── CircuitDisplay.test.tsx      # Test data and validation
├── README.md                    # Complete documentation
├── INTEGRATION_GUIDE.md         # Step-by-step integration
├── USAGE_EXAMPLES.tsx           # 15+ practical examples
├── DESIGN_SUMMARY.md            # This file
└── index.ts                     # Export file
```

## Next Steps

1. **Review Examples**
   - Run the demo: Visit `/circuits/demo`
   - Review different circuit types
   - Check styling and interactions

2. **Integration**
   - Follow `INTEGRATION_GUIDE.md` step-by-step
   - Replace old CircuitDisplay in SessionCard
   - Test with your existing circuit data

3. **Customization**
   - Adjust colors in `CIRCUIT_TYPE_CONFIG`
   - Modify metric colors in `METRIC_COLORS`
   - Add new circuit types as needed

4. **Testing**
   - Run manual testing checklist
   - Test with real circuit data from your API
   - Verify responsive behavior

5. **Documentation**
   - Update any internal docs that reference old CircuitDisplay
   - Share integration guide with team
   - Document any custom modifications

## Support

For issues or questions:
- Review `README.md` for comprehensive documentation
- Check `INTEGRATION_GUIDE.md` for integration help
- Refer to `USAGE_EXAMPLES.tsx` for code patterns
- Run tests in `CircuitDisplay.test.tsx` for validation

## Summary

The Circuit Display component provides:
- Visual distinction for circuit workouts
- Clear information hierarchy
- Color-coded metrics for quick scanning
- Comprehensive type coverage (AMRAP, EMOM, RFT, LADDER, etc.)
- Proper exercise formatting (reps, time, distance, calories)
- Prescribed weights display
- Rest time indicators
- Mobile-responsive design
- Accessibility compliance
- Easy integration with existing SessionCard

The design successfully differentiates circuit workouts from regular exercise blocks through distinct styling, color-coding, and structured layouts that make circuit workouts immediately recognizable.
