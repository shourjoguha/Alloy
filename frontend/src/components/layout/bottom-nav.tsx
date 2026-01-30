import { Link, useLocation } from '@tanstack/react-router';
import { User, Users } from 'lucide-react';
import { cn } from '@/lib/utils';

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { to: '/dashboard', label: 'Personal', icon: User },
  { to: '/teams', label: 'Teams', icon: Users },
];

export function BottomNav() {
  const location = useLocation();
  
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 safe-bottom border-t border-border bg-background-card/95 backdrop-blur supports-[backdrop-filter]:bg-background-card/80">
      <div className="container-app">
        <div className="flex h-16 items-center justify-around">
          {navItems.map((item) => {
            const isActive = location.pathname === item.to ||
              (item.to !== '/' && location.pathname.startsWith(item.to));

            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  'flex flex-col items-center justify-center gap-1 px-4 py-2 transition-colors',
                  isActive
                    ? 'text-primary'
                    : 'text-foreground-muted hover:text-foreground'
                )}
              >
                <div
                  className={cn(
                    'flex h-10 w-10 items-center justify-center rounded-full transition-colors',
                    isActive && 'bg-primary/10'
                  )}
                >
                  <item.icon className="h-5 w-5" />
                </div>
                <span className="text-xs font-medium">{item.label}</span>
              </Link>
            );
          })}

          {/* Page indicator dots */}
          <div className="flex items-center gap-1">
            {navItems.map((item, index) => {
              const isActive = location.pathname === item.to ||
                (item.to !== '/' && location.pathname.startsWith(item.to));
              return (
                <div
                  key={index}
                  className={cn(
                    'h-1.5 w-1.5 rounded-full transition-colors',
                    isActive ? 'bg-primary' : 'bg-foreground-subtle'
                  )}
                />
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}