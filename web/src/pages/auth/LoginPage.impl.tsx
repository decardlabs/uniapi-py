import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import * as z from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import Turnstile from '@/components/Turnstile';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { useSystemStatus } from '@/hooks/useSystemStatus';
import { api } from '@/lib/api';
import { buildGitHubOAuthUrl, getOAuthState } from '@/lib/oauth';
import { useAuthStore } from '@/lib/stores/auth';

const loginSchema = (t: (key: string) => string) =>
  z.object({
    username: z.string().min(1, t('auth.login.username_required')),
    password: z.string().min(1, t('auth.login.password_required')),
  });

type LoginForm = z.infer<ReturnType<typeof loginSchema>>;

export function LoginPage() {
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [accountLocked, setAccountLocked] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState('');
  const [turnstileRequired, setTurnstileRequired] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const { login } = useAuthStore();
  const { systemStatus } = useSystemStatus();
  const turnstileEnabled = Boolean(systemStatus?.turnstile_check);
  // Only show Turnstile after the server tells us it's required (i.e. after a failed login attempt).
  const turnstileRenderable = turnstileRequired && turnstileEnabled && Boolean(systemStatus?.turnstile_site_key);

  const form = useForm<LoginForm>({
    resolver: zodResolver(loginSchema(t)),
    defaultValues: { username: '', password: '' },
  });

  useEffect(() => {
    // Check for expired session
    if (searchParams.get('expired')) {
      console.warn(t('auth.login.session_expired'));
    }

    // Handle success messages from navigation state
    if (location.state?.message) {
      setSuccessMessage(location.state.message);
      // Clear the state to prevent showing the message on refresh
      window.history.replaceState({}, document.title);
    }
  }, [searchParams, location.state]);

  const onGitHubOAuth = async () => {
    if (!systemStatus.github_client_id) return;
    try {
      // Request state from backend to prevent CSRF
      const state = await getOAuthState();
      const redirectUri = `${window.location.origin}/oauth/github`;
      const url = buildGitHubOAuthUrl(systemStatus.github_client_id, state, redirectUri);
      window.location.href = url;
    } catch (e) {
      // Fallback: try without state if backend unavailable
      const redirectUri = `${window.location.origin}/oauth/github`;
      const url = buildGitHubOAuthUrl(systemStatus.github_client_id, '', redirectUri);
      window.location.href = url;
    }
  };

  const onSubmit = async (data: LoginForm) => {
    // Clear previous error states
    setAccountLocked(false);

    // Only gate on Turnstile if it's been required (after a prior failed attempt).
    if (turnstileRequired && turnstileEnabled && !turnstileToken) {
      form.setError('root', { message: t('auth.login.turnstile_required') });
      return;
    }
    setIsLoading(true);
    try {
      const payload: Record<string, string> = {
        username: data.username,
        password: data.password,
      };
      if (turnstileRequired && turnstileToken) {
        payload.turnstile = turnstileToken;
      }
      const response = await api.post('/api/user/login', payload);
      const { success, message, data: respData } = response.data;

      // Check if the server is now requiring Turnstile (after failed login).
      if (!success && respData?.turnstile_required) {
        setTurnstileRequired(true);
        setTurnstileToken('');
      }

      if (success) {
        login(respData, '');

        // Get redirect_to parameter from URL
        const redirectTo = searchParams.get('redirect_to');

        // Handle default root password warning
        if (data.username === 'root' && data.password === '123456') {
          navigate('/dashboard');
          console.warn(t('auth.login.root_password_warning'));
        } else if (redirectTo) {
          // Decode and navigate to the original page
          try {
            const decodedPath = decodeURIComponent(redirectTo);
            // Ensure the redirect path is safe (starts with /)
            if (decodedPath.startsWith('/')) {
              navigate(decodedPath);
            } else {
              navigate('/dashboard');
            }
          } catch (error) {
            console.error('Invalid redirect_to parameter:', error);
            navigate('/dashboard');
          }
        } else {
          navigate('/dashboard');
        }
      } else {
        // Handle attempts_remaining from server error data
        if (respData?.locked) {
          setAccountLocked(true);
        }
        if (respData && typeof respData.attempts_remaining === 'number') {
          form.setError('root', {
            message: `${t('auth.login.wrong_password')} ${t('auth.login.attempts_remaining', { count: respData.attempts_remaining })}`,
          });
        } else {
          form.setError('root', {
            message: message || t('auth.login.failed'),
          });
        }
      }
    } catch (error: any) {
      // Try to extract server response data from the axios error
      const respData = error?.response?.data;
      const extraData = respData?.data;

      if (extraData?.locked) {
        setAccountLocked(true);
      }

      if (extraData && typeof extraData.attempts_remaining === 'number') {
        form.setError('root', {
          message: `${t('auth.login.wrong_password')} ${t('auth.login.attempts_remaining', { count: extraData.attempts_remaining })}`,
        });
      } else {
        form.setError('root', {
          message: respData?.message || error?.message || t('auth.login.failed'),
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const hasOAuthOptions = systemStatus.github_oauth;

  const handleTurnstileVerify = (token: string) => {
    setTurnstileToken(token);
    if (form.formState.errors.root?.message) {
      form.clearErrors('root');
    }
  };

  const handleTurnstileExpire = () => {
    setTurnstileToken('');
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          {systemStatus.logo && (
            <div className="flex justify-center mb-4">
              <img
                src={systemStatus.logo}
                alt={systemStatus.system_name ? `${systemStatus.system_name} logo` : 'Site logo'}
                className="h-12 w-auto"
                decoding="async"
              />
            </div>
          )}
          <CardTitle className="text-2xl">
            {t('auth.login.title')}
            {systemStatus.system_name ? ` ${t('common.to')} ${systemStatus.system_name}` : ''}
          </CardTitle>
          <CardDescription>{t('auth.login.subtitle')}</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form data-testid="login-form" onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="username"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel htmlFor="login-username">{t('common.username')}</FormLabel>
                    <FormControl>
                      <Input id="login-username" autoComplete="username" {...field} />
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
                    <FormLabel htmlFor="login-password">{t('common.password')}</FormLabel>
                    <FormControl>
                      <Input id="login-password" type="password" autoComplete="current-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {successMessage && (
                <div className="text-sm text-success-foreground bg-success-muted p-3 rounded-md border border-success-border">
                  {successMessage}
                </div>
              )}
              {form.formState.errors.root && (
                <div className="text-sm text-destructive">{form.formState.errors.root.message}</div>
              )}
              {accountLocked && (
                <div className="text-sm text-destructive bg-destructive/10 p-4 rounded-md border border-destructive space-y-2">
                  <div className="font-semibold">{t('auth.login.locked_title')}</div>
                  <p>{t('auth.login.locked_message')}</p>
                  <Link
                    to="/reset"
                    className="text-primary hover:underline font-medium inline-block"
                  >
                    {t('auth.login.locked_action')}
                  </Link>
                </div>
              )}
              <Button
                type="submit"
                className="w-full"
                disabled={isLoading || (turnstileRequired && turnstileEnabled && !turnstileToken)}
              >
                {isLoading ? t('auth.login.signing_in') : t('auth.login.title')}
              </Button>

              {turnstileRenderable && systemStatus?.turnstile_site_key && (
                <Turnstile
                  siteKey={systemStatus.turnstile_site_key}
                  onVerify={handleTurnstileVerify}
                  onExpire={handleTurnstileExpire}
                  className="mt-2 flex justify-center"
                />
              )}

              <div className="text-center text-sm space-y-2">
                <Link to="/reset" className="text-primary hover:underline">
                  {t('auth.login.forgot_password')}
                </Link>
                <div>
                  {t('auth.login.no_account')}{' '}
                  <Link to="/register" className="text-primary hover:underline">
                    {t('auth.login.sign_up')}
                  </Link>
                </div>
              </div>
            </form>
          </Form>

          {hasOAuthOptions && (
            <>
              <Separator className="my-4" />
              <div className="text-center">
                <p className="text-sm text-muted-foreground mb-4">{t('auth.login.or_continue_with')}</p>
                <div className="flex justify-center gap-2">
                  {systemStatus.github_oauth && (
                    <Button variant="outline" size="sm" onClick={onGitHubOAuth}>
                      <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                      </svg>
                      GitHub
                    </Button>
                  )}
                  {/* WeChat OAuth: hidden until implementation is complete */}
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </main>
  );
}

export default LoginPage;
