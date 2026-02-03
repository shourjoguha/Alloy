import { cn } from '@/lib/utils';
import { ICON_MAPPINGS } from '@/config/onboarding-questions';
import { Dumbbell, Building } from 'lucide-react';

interface Slider5PointProps {
  value: Record<string, number>;
  onChange: (value: Record<string, number>) => void;
  options: Array<{ id: string; label: string }>;
  labels?: Record<number, string>;
}

// Icon component mapping for equipment
const ICON_COMPONENTS: Record<string, React.ComponentType<{ className?: string; strokeWidth?: number }>> = {
  'Dumbbell': Dumbbell,
  'Building': Building,
};

// Render the appropriate icon component
const renderIcon = (iconName: string) => {
  const IconComponent = ICON_COMPONENTS[iconName];
  if (!IconComponent) return null;
  return <IconComponent className="h-5 w-5 text-foreground/60" strokeWidth={1.5} />;
};

export function Slider5Point({ value, onChange, options, labels = {} }: Slider5PointProps) {
  return (
    <div className="space-y-4">
      {options.map((option) => {
        const iconName = ICON_MAPPINGS[option.id];
        return (
          <div key={option.id} className="space-y-2">
            <div className="flex items-center gap-2">
              {iconName && renderIcon(iconName)}
              <span className="text-xs text-foreground-muted/70 font-medium">{option.label}</span>
              <span className="ml-auto text-xs text-foreground-muted/50">
                {value[option.id] ? labels[value[option.id]] || `${value[option.id]}/5` : 'Not selected'}
              </span>
            </div>
            <div className="relative px-1">
              <input
                type="range"
                min={1}
                max={5}
                step={1}
                value={value[option.id] || 0}
                onChange={(e) => onChange({ ...value, [option.id]: Number(e.target.value) })}
                className="w-full h-2 bg-background-input/50 rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <div className="flex justify-between mt-1.5 px-1">
                {[1, 2, 3, 4, 5].map((num) => (
                  <span
                    key={num}
                    className={cn(
                      'text-xs transition-colors',
                      value[option.id] >= num ? 'text-foreground/90 font-medium' : 'text-foreground-muted/50'
                    )}
                  >
                    {num}
                  </span>
                ))}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
