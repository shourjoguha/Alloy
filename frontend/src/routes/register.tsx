import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuthStore } from '@/stores/auth-store';
import { register } from '@/api/auth';
import { useUIStore } from '@/stores/ui-store';
import { useState } from 'react';
import { AuthBackground } from '@/components/auth/AuthBackground';
import '@/styles/landing.css';

const registerSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Invalid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

type RegisterFormValues = z.infer<typeof registerSchema>;

export const Route = createFileRoute('/register')({
  component: RegisterPage,
});

function RegisterPage() {
  const navigate = useNavigate();
  const { setToken, setUser, setAuthenticated } = useAuthStore();
  const { addToast } = useUIStore();
  const [isLoading, setIsLoading] = useState(false);

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      name: '',
      email: '',
      password: '',
      confirmPassword: '',
    },
  });

  const onSubmit = async (data: RegisterFormValues) => {
    setIsLoading(true);
    try {
      const response = await register(data.email, data.password, data.name);
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
        message: 'Account created successfully',
      });
      navigate({ to: '/dashboard' });
    } catch (error: any) {
      addToast({
        type: 'error',
        message: error.response?.data?.detail || 'Registration failed. Please try again.',
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
            <h1 className="auth-title">Create Account</h1>
            <p className="auth-subtitle">Enter your details to get started with Alloy</p>
          </div>

          <form onSubmit={form.handleSubmit(onSubmit)} className="auth-form">
            <div className="form-group">
              <Label htmlFor="name" className="auth-label">Name</Label>
              <Input
                id="name"
                placeholder="John Doe"
                error={!!form.formState.errors.name}
                {...form.register('name')}
                className="auth-input"
              />
              {form.formState.errors.name && (
                <p className="auth-error">{form.formState.errors.name.message}</p>
              )}
            </div>

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

            <div className="form-group">
              <Label htmlFor="confirmPassword" className="auth-label">Confirm Password</Label>
              <Input
                id="confirmPassword"
                type="password"
                error={!!form.formState.errors.confirmPassword}
                {...form.register('confirmPassword')}
                className="auth-input"
              />
              {form.formState.errors.confirmPassword && (
                <p className="auth-error">{form.formState.errors.confirmPassword.message}</p>
              )}
            </div>

            <Button type="submit" className="auth-button" isLoading={isLoading}>
              Register
            </Button>
          </form>

          <div className="auth-footer">
            <p className="auth-footer-text">
              Already have an account?{' '}
              <Link to="/login" className="auth-link">
                Login
              </Link>
            </p>
          </div>
        </div>
      </div>
    </AuthBackground>
  );
}
