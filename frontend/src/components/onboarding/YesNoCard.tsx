import { cn } from '@/lib/utils';
import { ICON_MAPPINGS } from '@/config/onboarding-questions';
import { ArrowDown, ArrowUp, Trophy, Footprints, Dumbbell, Zap, Target, Activity } from 'lucide-react';

interface YesNoCardProps {
  value: Record<string, boolean>;
  onChange: (value: Record<string, boolean>) => void;
  options: Array<{ id: string; label: string; description?: string }>;
}

// Icon component mapping for movements
const ICON_COMPONENTS: Record<string, React.ComponentType<{ className?: string; strokeWidth?: number }>> = {
  'ArrowDown': ArrowDown,
  'ArrowUp': ArrowUp,
  'Trophy': Trophy,
  'Footprints': Footprints,
  'Dumbbell': Dumbbell,
  'Zap': Zap,
  'Target': Target,
  'Activity': Activity,
};

// Render the appropriate icon component
const renderIcon = (iconName: string) => {
  const IconComponent = ICON_COMPONENTS[iconName];
  if (!IconComponent) return null;
  return <IconComponent className="h-5 w-5 text-foreground/60" strokeWidth={1.5} />;
};

export function YesNoCard({ value, onChange, options }: YesNoCardProps) {
  return (
    <div className="space-y-3">
      {options.map((option) => {
        const iconName = ICON_MAPPINGS[option.id];
        return (
          <div key={option.id} className="flex items-center justify-between gap-4 p-3 rounded-lg border border-border/20 bg-background-card hover:bg-background-secondary/30 transition-all">
            <div className="flex items-center gap-3 flex-1 min-w-0">
              {iconName && renderIcon(iconName)}
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-sm">{option.label}</h3>
                {option.description && (
                  <p className="text-xs text-foreground-muted/70 mt-0.5 truncate">{option.description}</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => onChange({ ...value, [option.id]: false })}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                  value[option.id] === false
                    ? 'bg-error/10 text-error border border-error/20'
                    : 'bg-background-input text-foreground-muted/60 hover:bg-background-input/80 border border-border/20'
                )}
              >
                No
              </button>
              <button
                type="button"
                onClick={() => onChange({ ...value, [option.id]: true })}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                  value[option.id] === true
                    ? 'bg-success/10 text-success border border-success/20'
                    : 'bg-background-input text-foreground-muted/60 hover:bg-background-input/80 border border-border/20'
                )}
              >
                Yes
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
