import { Link, useRouter } from '@tanstack/react-router';
import { Bell, Menu, ArrowLeft } from 'lucide-react';
import { useUIStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';

export function Header() {
  const router = useRouter();
  const { toggleMenu } = useUIStore();
  const { isAuthenticated } = useAuthStore();
  
  const canGoBack = router.history.length > 1;
  const isRootPath = router.state.location.pathname === '/';

  return (
    <header className="sticky top-0 z-40 safe-top bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="container-app flex h-14 items-center justify-between">
        {/* Left side - Back button or Logo */}
        <div className="flex items-center gap-2">
          {!isRootPath && canGoBack ? (
            <button
              onClick={() => router.history.back()}
              className="flex h-10 w-10 items-center justify-center rounded-lg text-foreground-muted transition-colors hover:bg-background-secondary hover:text-foreground"
              aria-label="Go back"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
          ) : (
            <Link to={isAuthenticated ? '/dashboard' : '/'} className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
                <span className="text-sm font-bold text-background">G</span>
              </div>
              <span className="text-lg font-semibold text-foreground">Gainsly</span>
            </Link>
          )}
        </div>

        {/* Right side - Notifications and Menu */}
        <div className="flex items-center gap-1">
          <button
            className="flex h-10 w-10 items-center justify-center rounded-lg text-foreground-muted transition-colors hover:bg-background-secondary hover:text-foreground"
            aria-label="Notifications"
          >
            <Bell className="h-5 w-5" />
          </button>
          <button
            onClick={toggleMenu}
            className="flex h-10 w-10 items-center justify-center rounded-lg text-foreground-muted transition-colors hover:bg-background-secondary hover:text-foreground"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
