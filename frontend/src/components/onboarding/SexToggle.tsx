import { cn } from '@/lib/utils';
import { User } from 'lucide-react';

interface SexOption {
  value: string;
  label: string;
}

const SEX_OPTIONS: SexOption[] = [
  { value: 'male', label: 'Male' },
  { value: 'female', label: 'Female' },
  { value: 'intersex', label: 'Intersex' },
  { value: 'unspecified', label: 'Prefer not to say' },
];

interface SexToggleProps {
  value: string | null;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function SexToggle({ value, onChange, disabled = false }: SexToggleProps) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {SEX_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          disabled={disabled}
          className={cn(
            'flex flex-col items-center justify-center gap-2 p-4 rounded-lg border transition-all duration-200',
            value === option.value
              ? 'border-primary/50 bg-primary/5'
              : 'border-border/30 bg-background-card hover:bg-background-secondary/50 hover:border-border/50',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        >
          <User className="h-6 w-6 text-foreground/70" strokeWidth={1.5} />
          <span className="text-sm font-medium">{option.label}</span>
        </button>
      ))}
    </div>
  );
}