import Turnstile from '@/components/Turnstile';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { useNotifications } from '@/components/ui/notifications';
import { api } from '@/lib/api';
import { useAuthStore } from '@/lib/stores/auth';
import { loadSystemStatus, type SystemStatus } from '@/lib/utils';
import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import * as z from 'zod';

const personalSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  display_name: z.string().optional(),
  email: z.string().email('Valid email is required').optional(),
});

type PersonalForm = z.infer<typeof personalSchema>;

export function PersonalSettings() {
  const { t } = useTranslation();
  const { user, updateUser } = useAuthStore();
  const { notify } = useNotifications();
  const [loading, setLoading] = useState(false);

  // System status state
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({});
  const [emailVerificationCode, setEmailVerificationCode] = useState('');
  const [emailAction, setEmailAction] = useState<'send' | 'bind' | null>(null);
  const [emailVerificationError, setEmailVerificationError] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');

  // Password change state
  const [newPassword, setNewPassword] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordError, setPasswordError] = useState('');

  const turnstileEnabled = Boolean(systemStatus.turnstile_check);
  const turnstileRenderable = turnstileEnabled && Boolean(systemStatus.turnstile_site_key);

  // Load system status
  const loadStatus = async () => {
    try {
      const status = await loadSystemStatus();
      if (status) {
        setSystemStatus(status);
      }
    } catch (error) {
      console.error('Failed to load system status:', error);
    }
  };

  const form = useForm<PersonalForm>({
    resolver: zodResolver(personalSchema),
    defaultValues: {
      username: user?.username || '',
      display_name: user?.display_name || '',
      email: user?.email || '',
    },
  });

  const syncProfile = (profile: PersonalForm) => {
    updateUser(profile);
    form.reset({
      username: profile.username || '',
      display_name: profile.display_name || '',
      email: profile.email || '',
    });
    setEmailVerificationCode('');
    setEmailVerificationError('');
  };

  const loadProfile = async (showNotification = false) => {
    try {
      const response = await api.get('/api/user/self');
      const { success, message, data } = response.data;
      if (success && data) {
        syncProfile({
          username: data.username || '',
          display_name: data.display_name || '',
          email: data.email || '',
        });
        return true;
      }

      const errorMessage = message || t('personal_settings.profile_info.load_failed');
      form.setError('root', { message: errorMessage });
      if (showNotification) {
        notify({
          type: 'error',
          message: errorMessage,
        });
      }
      return false;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('personal_settings.profile_info.load_failed');
      form.setError('root', { message: errorMessage });
      if (showNotification) {
        notify({
          type: 'error',
          message: errorMessage,
        });
      }
      return false;
    }
  };

  useEffect(() => {
    loadStatus();
    loadProfile();
  }, []);

  const sendEmailVerificationCode = async () => {
    const email = form.getValues('email')?.trim() || '';
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(email)) {
      form.setError('email', {
        message: t('auth.register.email_invalid'),
      });
      return;
    }

    if (turnstileEnabled && !turnstileToken) {
      form.setError('email', {
        message: t('auth.login.turnstile_required'),
      });
      return;
    }

    setEmailAction('send');
    setEmailVerificationError('');

    try {
      const turnstileParam = turnstileEnabled && turnstileToken ? `&turnstile=${encodeURIComponent(turnstileToken)}` : '';
      const response = await api.get(`/api/verification?email=${encodeURIComponent(email)}${turnstileParam}`);
      const { success, message } = response.data;

      if (success) {
        form.clearErrors('email');
        notify({
          type: 'success',
          message: message || t('personal_settings.profile_info.send_code_success'),
        });
        if (turnstileEnabled) {
          setTurnstileToken('');
        }
        return;
      }

      form.setError('email', {
        message: message || t('personal_settings.profile_info.failed'),
      });
    } catch (error) {
      form.setError('email', {
        message: error instanceof Error ? error.message : t('personal_settings.profile_info.failed'),
      });
    } finally {
      setEmailAction(null);
    }
  };

  const bindEmail = async () => {
    const email = form.getValues('email')?.trim() || '';
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(email)) {
      form.setError('email', {
        message: t('auth.register.email_invalid'),
      });
      return;
    }

    if (!emailVerificationCode.trim()) {
      setEmailVerificationError(t('auth.register.verification_code_required'));
      return;
    }

    setEmailAction('bind');
    setEmailVerificationError('');

    try {
      const response = await api.get(
        `/api/oauth/email/bind?email=${encodeURIComponent(email)}&code=${encodeURIComponent(emailVerificationCode.trim())}`
      );
      const { success, message } = response.data;

      if (success) {
        await loadProfile();
        notify({
          type: 'success',
          message: t('personal_settings.profile_info.bind_success'),
        });
        return;
      }

      setEmailVerificationError(message || t('personal_settings.profile_info.failed'));
    } catch (error) {
      setEmailVerificationError(error instanceof Error ? error.message : t('personal_settings.profile_info.failed'));
    } finally {
      setEmailAction(null);
    }
  };

  const onSubmit = async (data: PersonalForm) => {
    setLoading(true);
    try {
      const payload = { ...data };
      delete (payload as Record<string, unknown>).email;

      const response = await api.put('/api/user/self', payload);
      const { success, message } = response.data;
      if (success) {
        const refreshed = await loadProfile();
        if (!refreshed) {
          syncProfile({ ...data });
        }
        notify({
          type: 'success',
          message: message || t('personal_settings.profile_info.success'),
        });
      } else {
        form.setError('root', {
          message: message || t('personal_settings.profile_info.failed'),
        });
      }
    } catch (error) {
      form.setError('root', {
        message: error instanceof Error ? error.message : t('personal_settings.profile_info.failed'),
      });
    } finally {
      setLoading(false);
    }
  };

  // Update password
  const updatePassword = async () => {
    setPasswordError('');
    if (!newPassword || !currentPassword) {
      setPasswordError(t('personal_settings.security.password.required'));
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError(t('personal_settings.security.password.mismatch'));
      return;
    }

    setPasswordLoading(true);
    try {
      const response = await api.put('/api/user/self', { password: newPassword, old_password: currentPassword });
      const { success, message } = response.data;
      if (success) {
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
        notify({
          type: 'success',
          message: t('personal_settings.security.password.success'),
        });
      } else {
        setPasswordError(message || t('personal_settings.security.password.failed'));
      }
    } catch (error) {
      setPasswordError(error instanceof Error ? error.message : t('personal_settings.security.password.failed'));
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Profile Information Card */}
      <Card>
        <CardHeader>
          <CardTitle>{t('personal_settings.profile_info.title')}</CardTitle>
          <CardDescription>{t('personal_settings.profile_info.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="username"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('personal_settings.profile_info.username')}</FormLabel>
                      <FormControl>
                        <Input {...field} disabled />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="display_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('personal_settings.profile_info.display_name')}</FormLabel>
                      <FormControl>
                        <Input placeholder={t('personal_settings.profile_info.display_name_placeholder')} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem className="space-y-3">
                    <FormLabel>{t('personal_settings.profile_info.email')}</FormLabel>
                    <FormControl>
                      <Input type="email" placeholder={t('personal_settings.profile_info.email_placeholder')} {...field} />
                    </FormControl>
                    <div className="flex flex-col gap-3">
                      <p className="text-sm text-muted-foreground">{t('personal_settings.profile_info.email_help')}</p>
                      <div className="flex flex-col gap-3 md:flex-row items-end">
                        <div className="flex-1 w-full space-y-1">
                          <Input
                            value={emailVerificationCode}
                            onChange={(e) => {
                              setEmailVerificationCode(e.target.value);
                              if (emailVerificationError) {
                                setEmailVerificationError('');
                              }
                            }}
                            placeholder={t('personal_settings.profile_info.email_verification_code_placeholder')}
                          />
                        </div>
                        <div className="flex flex-col gap-2 sm:flex-row flex-shrink-0">
                          <Button
                            type="button"
                            variant="outline"
                            onClick={sendEmailVerificationCode}
                            disabled={emailAction !== null || (turnstileEnabled && !turnstileToken)}
                          >
                            {emailAction === 'send'
                              ? t('personal_settings.profile_info.sending_code')
                              : t('personal_settings.profile_info.send_code')}
                          </Button>
                          <Button type="button" onClick={bindEmail} disabled={emailAction !== null}>
                            {emailAction === 'bind'
                              ? t('personal_settings.profile_info.binding_email')
                              : t('personal_settings.profile_info.bind_email')}
                          </Button>
                        </div>
                      </div>
                      {turnstileRenderable && systemStatus.turnstile_site_key && (
                        <Turnstile
                          siteKey={systemStatus.turnstile_site_key}
                          onVerify={(token) => setTurnstileToken(token)}
                          onExpire={() => setTurnstileToken('')}
                        />
                      )}
                      {emailVerificationError && <div className="text-sm text-destructive">{emailVerificationError}</div>}
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {form.formState.errors.root && <div className="text-sm text-destructive">{form.formState.errors.root.message}</div>}

              <Button type="submit" disabled={loading}>
                {loading ? t('personal_settings.profile_info.updating') : t('personal_settings.profile_info.update_button')}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>

      {/* Password Change Card */}
      <Card>
        <CardHeader>
          <CardTitle>{t('personal_settings.security.password.title')}</CardTitle>
          <CardDescription>{t('personal_settings.security.password.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {passwordError && <div className="text-sm text-destructive font-medium">{passwordError}</div>}

          <div className="space-y-3">
            <div className="space-y-1">
              <FormLabel>{t('personal_settings.security.password.current_password')}</FormLabel>
              <Input
                type="password"
                placeholder={t('personal_settings.security.password.current_password_placeholder')}
                value={currentPassword}
                onChange={(e) => {
                  setCurrentPassword(e.target.value);
                  if (passwordError) setPasswordError('');
                }}
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <FormLabel>{t('personal_settings.security.password.new_password')}</FormLabel>
                <Input
                  type="password"
                  placeholder={t('personal_settings.security.password.new_password_placeholder')}
                  value={newPassword}
                  onChange={(e) => {
                    setNewPassword(e.target.value);
                    if (passwordError) setPasswordError('');
                  }}
                />
              </div>
              <div className="space-y-1">
                <FormLabel>{t('personal_settings.security.password.confirm_password')}</FormLabel>
                <Input
                  type="password"
                  placeholder={t('personal_settings.security.password.confirm_password_placeholder')}
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    if (passwordError) setPasswordError('');
                  }}
                />
              </div>
            </div>
          </div>
          <Button onClick={updatePassword} disabled={passwordLoading} className="w-full md:w-auto">
            {passwordLoading ? t('personal_settings.security.password.updating') : t('personal_settings.security.password.update_button')}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default PersonalSettings;
