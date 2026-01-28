# Soreness Logger UI Redesign Plan

## Overview
Redesign the soreness logging page with improved aesthetics, condensed region selection, better visual hierarchy, and enhanced user experience.

## Changes Required

### 1. **Region Selector Component** (`RegionSelector.tsx` - NEW)
- Create a single dropdown to replace the 6 expandable zone cards
- Options: Posterior Upper, Anterior Upper, Shoulder, Core, Posterior Lower, Anterior Lower
- When a region is selected, show:
  - Region-level soreness selector (1-5 buttons) that applies to all muscles in region
  - Individual muscle list for that region with per-muscle soreness controls
  - "Apply to all muscles" toggle for the region

### 2. **Logged Muscles Display** (`LoggedMuscles.tsx` - NEW)
- Create a horizontal scrollable card strip below the 2D figure
- Each card shows: muscle name, soreness level (color-coded), and remove button
- Cards use the accent color scheme matching soreness levels
- Smooth animations for adding/removing cards

### 3. **HumanBodyMap Enhancements** (`HumanBodyMap.tsx`)
- **Improved spacing**: Adjust SVG paths to add gaps between muscles (reduce overlap)
- **View-based fading**: 
  - When viewing front: Back muscles show at 30% opacity
  - When viewing back: Front muscles show at 30% opacity
  - Currently viewed side muscles remain at 100% opacity
- **Enhanced hover states**: Scale up slightly and add glow effect
- **Better tap targets**: Add transparent padding around paths for easier mobile selection

### 4. **Layout Restructure** (`SorenessTracker.tsx`)
- Move from 2-column to vertical layout:
  - Top: Title and instructions
  - Middle: 2D body figure (centered)
  - Below figure: Front/Back toggle and legend
  - Below that: Region dropdown selector
  - Below that: Logged muscles cards strip
  - Bottom: Notes textarea and Submit/Cancel buttons
- Ensure all text wraps properly with `break-words`, `truncate`, or `line-clamp` utilities
- Use consistent spacing (gap-4, gap-6) to prevent overlaps

### 5. **Typography & Fonts** (Update `globals.css`)
- Add new font families for hierarchy:
  - Headings: Use `font-semibold` with tighter letter-spacing
  - Body text: Use `font-regular` with improved line-height
  - Labels/buttons: Use `font-medium` for emphasis
- Add font size variants for better visual hierarchy
- Ensure all text has `text-wrap: balance` or `text-wrap: pretty` for natural line breaks

### 6. **Visual Design Improvements**
- **Color-coded soreness levels**:
  - 0 (None): slate-100/slate-800
  - 1 (Minimal): emerald-100/emerald-800
  - 2 (Mild): teal-100/teal-800
  - 3 (Moderate): yellow-100/yellow-800
  - 4 (Significant): orange-100/orange-800
  - 5 (Severe): red-100/red-800
- **Card styling**: Use consistent rounded-xl, subtle shadows, smooth transitions
- **Interactive states**: Add hover/active/pressed states with visual feedback
- **Accessibility**: Ensure sufficient color contrast (WCAG AA)

### 7. **Component Refactoring**
- Extract region selection logic into `useRegionSelector` hook
- Extract logged muscles management into `useLoggedMuscles` hook
- Keep API integration logic (`useLogSoreness`) unchanged
- Maintain backward compatibility with existing data structures

## File Changes Summary
1. **Create**: `frontend/src/components/visuals/RegionSelector.tsx`
2. **Create**: `frontend/src/components/visuals/LoggedMuscles.tsx`
3. **Modify**: `frontend/src/components/visuals/HumanBodyMap.tsx` (enhance spacing, add view fading)
4. **Modify**: `frontend/src/components/visuals/SorenessTracker.tsx` (restructure layout, integrate new components)
5. **Modify**: `frontend/src/styles/globals.css` (add typography enhancements)
6. **Delete**: `frontend/src/components/visuals/MuscleList.tsx` (replaced by RegionSelector)

## Key Design Decisions
- **Single dropdown** for regions reduces cognitive load and visual clutter
- **Vertical layout** works better on mobile and allows for larger, more touchable elements
- **Logged muscles as cards** provides immediate visual feedback of what's being logged
- **View-based fading** provides clear visual cues for which muscles are selectable
- **Improved spacing** in the 2D figure reduces selection errors