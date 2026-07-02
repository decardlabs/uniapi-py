import Turnstile from '@/components/Turnstile';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { useSystemStatus } from '@/hooks/useSystemStatus';
import { api } from '@/lib/api';
import { buildGitHubOAuthUrl, getOAuthState } from '@/lib/oauth';
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import * as z from 'zod';

const registerSchema = (t: (key: string) => string) =>
  z
    .object({
      username: z.string().min(3, t('auth.register.username_min_length')),
      password: z
        .string()
        .min(8, t('auth.register.password_min_length'))
        .refine((val) => /[A-Z]/.test(val), {
          message: t('auth.register.password_uppercase') || 'Password must contain at least one uppercase letter',
        })
        .refine((val) => /\d/.test(val), {
          message: t('auth.register.password_digit') || 'Password must contain at least one digit',
        }),
      password2: z.string().min(8, t('auth.register.password_confirm_required')),
      email: z.string().email(t('auth.register.email_required')),
      verification_code: z.string().min(1, t('auth.register.verification_code_required')),
    })
    .refine((data) => data.password === data.password2, {
      message: t('auth.register.passwords_mismatch'),
      path: ['password2'],
    });

type RegisterForm = z.infer<ReturnType<typeof registerSchema>>;

export function RegisterPage() {
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(false);
  const [isEmailSent, setIsEmailSent] = useState(false);
  const [emailVerificationError, setEmailVerificationError] = useState('');
  const [turnstileToken, setTurnstileToken] = useState<string>('');
  const navigate = useNavigate();
  const { systemStatus } = useSystemStatus();

  const form = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema(t)),
    defaultValues: {
      username: '',
      password: '',
      password2: '',
      email: '',
      verification_code: '',
    },
  });

  // Watch email field to enable/disable send code button
  const emailValue = form.watch('email');

  const onGitHubOAuth = async () => {
    const clientId = systemStatus?.github_client_id;
    if (!clientId) return;
    try {
      const state = await getOAuthState();
      const redirectUri = `${window.location.origin}/oauth/github`;
      window.location.href = buildGitHubOAuthUrl(clientId, state, redirectUri);
    } catch (e) {
      const redirectUri = `${window.location.origin}/oauth/github`;
      window.location.href = buildGitHubOAuthUrl(clientId, '', redirectUri);
    }
  };

  const sendVerificationCode = async () => {
    const email = form.getValues('email');

    // Simple email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email)) {
      form.setError('email', { message: t('auth.register.email_invalid') });
      return;
    }

    try {
      setIsLoading(true);
      const body: Record<string, string> = { email };
      if (systemStatus?.turnstile_check && turnstileToken) {
        body.turnstile = turnstileToken;
      }
      const response = await api.post('/api/verification', body);
      const { success, message } = response.data;

      if (success) {
        setIsEmailSent(true);
        setEmailVerificationError('');
      } else {
        setEmailVerificationError(message || t('auth.register.send_code_failed'));
      }
    } catch (error: any) {
      setEmailVerificationError(error?.response?.data?.message || error?.message || t('auth.register.send_code_failed'));
    } finally {
      setIsLoading(false);
    }
  };

  const onSubmit = async (data: RegisterForm) => {
    setIsLoading(true);
    try {
      const payload = {
        username: data.username,
        password: data.password,
        email: data.email,
        verification_code: data.verification_code,
      };

      // Unified API call - complete URL with /api prefix
      if (systemStatus?.turnstile_check && turnstileToken) {
        (payload as any).turnstile = turnstileToken;
      }
      const response = await api.post('/api/user/register', payload);
      const body = response.data;

      // Handle both GenericApiResponse format ({success, message}) and
      // http_exception_handler format ({detail, success, error: {message}})
      const success = body.success;
      const message = body.message || body.detail || body.error?.message || '';

      if (success) {
        navigate('/login', {
          state: { message: t('auth.register.success') },
        });
      } else {
        // Map backend error messages to the correct form field
        const msg = message.toLowerCase();
        if (msg.includes('username')) {
          form.setError('username', { message });
        } else if (msg.includes('password') || msg.includes('uppercase') || msg.includes('digit') || msg.includes('special') || msg.includes('character')) {
          form.setError('password', { message });
        } else if (msg.includes('验证码') || msg.includes('code')) {
          form.setError('verification_code', { message });
        } else {
          form.setError('root', {
            message: message || t('auth.register.failed'),
          });
        }
      }
    } catch (error: any) {
      form.setError('root', {
        message: error?.response?.data?.message || error?.message || t('auth.register.failed'),
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">{t('auth.register.title')}</CardTitle>
          <CardDescription>{t('auth.register.subtitle')}</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="username"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('common.username')}</FormLabel>
                    <FormControl>
                      <Input placeholder={t('auth.register.enter_username')} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('common.password')}</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder={t('auth.register.enter_password')} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password2"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('auth.register.confirm_password')}</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder={t('auth.register.confirm_password')} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('common.email')}</FormLabel>
                    <FormControl>
                      <div className="flex gap-2">
                        <Input type="email" placeholder={t('auth.register.enter_email')} {...field} className="flex-1" />
                        <Button
                          type="button"
                          variant="outline"
                          onClick={sendVerificationCode}
                          disabled={
                            isLoading ||
                            !emailValue ||
                            !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailValue) ||
                            (systemStatus?.turnstile_check && !turnstileToken)
                          }
                        >
                          {isLoading ? t('auth.register.sending') : isEmailSent ? t('auth.register.sent') : t('auth.register.send_code')}
                        </Button>
                      </div>
                      {emailVerificationError && (
                        <div className="text-sm text-destructive">{emailVerificationError}</div>
                      )}
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="verification_code"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('auth.register.verification_code')}</FormLabel>
                    <FormControl>
                      <Input placeholder={t('auth.register.enter_verification_code')} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {form.formState.errors.root && <div className="text-sm text-destructive">{form.formState.errors.root.message}</div>}

              <Button type="submit" className="w-full" disabled={isLoading || (systemStatus?.turnstile_check && !turnstileToken)}>
                {isLoading ? t('auth.register.creating') : t('auth.register.title')}
              </Button>

              {systemStatus?.turnstile_check && systemStatus?.turnstile_site_key && (
                <div className="mt-2">
                  <Turnstile
                    siteKey={systemStatus.turnstile_site_key}
                    onVerify={(token) => setTurnstileToken(token)}
                    onExpire={() => setTurnstileToken('')}
                    className="flex justify-center"
                  />
                </div>
              )}

              {systemStatus?.github_oauth && (
                <div className="space-y-2">
                  <div className="relative">
                    <div className="absolute inset-0 flex items-center">
                      <span className="w-full border-t" />
                    </div>
                    <div className="relative flex justify-center text-xs">
                      <span className="bg-card px-2 text-muted-foreground">{t('auth.register.or_sign_up_with')}</span>
                    </div>
                  </div>
                  <Button type="button" variant="outline" className="w-full" onClick={onGitHubOAuth}>
                    <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                    </svg>
                    GitHub
                  </Button>
                </div>
              )}

              <div className="text-center text-sm">
                {t('auth.register.already_have_account')}{' '}
                <Link to="/login" className="text-primary hover:underline">
                  {t('auth.register.sign_in')}
                </Link>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </main>
  );
}

export default RegisterPage;
