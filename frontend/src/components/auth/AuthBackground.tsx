import { ReactNode } from 'react';

// Generate particles once at module level to avoid Math.random() in render
const particles = Array.from({ length: 30 }, (_, i) => ({
  id: i,
  left: Math.random() * 100,
  delay: Math.random() * 20,
  duration: 15 + Math.random() * 10
}));

export function AuthBackground({ children }: { children: ReactNode }) {
  return (
    <div className="auth-background">
      <div className="background-particles">
        {particles.map((particle) => (
          <div
            key={particle.id}
            className="particle"
            style={{
              left: `${particle.left}%`,
              animationDelay: `${particle.delay}s`,
              animationDuration: `${particle.duration}s`
            }}
          />
        ))}
      </div>
      {children}
    </div>
  );
}
