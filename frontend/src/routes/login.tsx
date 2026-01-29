import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuthStore } from '@/stores/auth-store';
import { login } from '@/api/auth';
import { useUIStore } from '@/stores/ui-store';
import { useState } from 'react';
import { AuthBackground } from '@/components/auth/AuthBackground';
import '@/styles/landing.css';

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export const Route = createFileRoute('/login')({
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { setToken, setUser, setAuthenticated } = useAuthStore();
  const { addToast } = useUIStore();
  const [isLoading, setIsLoading] = useState(false);

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const onSubmit = async (data: LoginFormValues) => {
    setIsLoading(true);
    try {
      const response = await login(data.email, data.password);
      setToken(response.access_token);
      setAuthenticated(true);
      
      try {
        const { verifyToken } = await import('@/api/auth');
        const user = await verifyToken(response.access_token);
        setUser(user);
      } catch (e) {
        console.error('Failed to fetch user details', e);
      }

      addToast({
        type: 'success',
        message: 'Logged in successfully',
      });
      navigate({ to: '/dashboard' });
    } catch (error: any) {
      addToast({
        type: 'error',
        message: error.response?.data?.detail || 'Login failed. Please check your credentials.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthBackground>
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-header">
            <h1 className="auth-title">Welcome Back</h1>
            <p className="auth-subtitle">Enter your credentials to access Alloy</p>
          </div>

          <form onSubmit={form.handleSubmit(onSubmit)} className="auth-form">
            <div className="form-group">
              <Label htmlFor="email" className="auth-label">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="your@email.com"
                error={!!form.formState.errors.email}
                {...form.register('email')}
                className="auth-input"
              />
              {form.formState.errors.email && (
                <p className="auth-error">{form.formState.errors.email.message}</p>
              )}
            </div>

            <div className="form-group">
              <Label htmlFor="password" className="auth-label">Password</Label>
              <Input
                id="password"
                type="password"
                error={!!form.formState.errors.password}
                {...form.register('password')}
                className="auth-input"
              />
              {form.formState.errors.password && (
                <p className="auth-error">{form.formState.errors.password.message}</p>
              )}
            </div>

            <Button type="submit" className="auth-button" isLoading={isLoading}>
              Login
            </Button>
          </form>

          <div className="auth-footer">
            <p className="auth-footer-text">
              Don't have an account?{' '}
              <Link to="/register" className="auth-link">
                Register
              </Link>
            </p>
          </div>
        </div>
      </div>
    </AuthBackground>
  );
}
