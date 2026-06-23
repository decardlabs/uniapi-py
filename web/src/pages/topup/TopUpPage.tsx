import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { ResponsivePageContainer } from '@/components/ui/responsive-container';
import { useNotifications } from '@/components/ui/notifications';
import { api } from '@/lib/api';
import { getSelfRechargeRequests, createRechargeRequest } from '@/lib/services/recharge';
import { useAuthStore } from '@/lib/stores/auth';
import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import * as z from 'zod';

interface UserInfo {
  id: number; // eslint-disable-line @typescript-eslint/no-explicit-any
  username: string;
  display_name?: string;
  quota: number;
}

interface TopUpRequest {
  id: number;
  user_id: number;
  amount: number;
  quota: number;
  status: number;
  remark: string;
  admin_remark: string;
  created_time: number;
}

export function TopUpPage() {
  const { user, updateUser } = useAuthStore();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [userBalance, setUserBalance] = useState(user?.balance || 0);
  const [topUpLink, setTopUpLink] = useState('');
  const [userData, setUserData] = useState<UserInfo | null>(null);
  const [myRequests, setMyRequests] = useState<TopUpRequest[]>([]);
  const { t } = useTranslation();
  const { notify } = useNotifications();
  const MICRO_PER_YUAN = 1_000_000; // 1 yuan = 1,000,000 micro-yuan

  const tr = (key: string, defaultValue: string) =>
    t(`topup.${key}`, { defaultValue });

  const loadUserData = async () => {
    try {
      const res = await api.get('/api/user/self');
      const { success, data } = res.data;
      if (success) {
        setUserBalance(data.balance ?? 0);
        setUserData(data);
        updateUser(data);
      }
    } catch (error) {
      console.error('Error loading user data:', error);
    }
  };

  const loadSystemStatus = () => {
    const status = localStorage.getItem('status');
    if (status) {
      try {
        const statusData = JSON.parse(status);
        if (statusData.top_up_link) {
          setTopUpLink(statusData.top_up_link);
        }
      } catch (error) {
        console.error('Error parsing system status:', error);
      }
    }
  };

  const loadMyRequests = async () => {
    try {
      const res = await getSelfRechargeRequests({ p: 1, size: 10 });
      if (res.data?.success) {
        setMyRequests(res.data.data || []);
      }
    } catch (error) {
      console.error('Error loading recharge requests:', error);
    }
  };

  const openTopUpLink = () => {
    if (!topUpLink) return;
    try {
      const url = new URL(topUpLink);
      if (userData) {
        url.searchParams.append('username', userData.username);
        url.searchParams.append('user_id', userData.id.toString());
        url.searchParams.append('transaction_id', crypto.randomUUID());
      }
      window.open(url.toString(), '_blank');
    } catch (error) {
      console.error('Error opening top-up link:', error);
    }
  };

  // Recharge request form
  const rechargeSchema = z.object({
    amount: z.coerce.number().min(0.0001, tr('request.amount_required', 'Amount must be greater than 0')),
    remark: z.string().optional(),
  });
  type RechargeForm = z.infer<typeof rechargeSchema>;
  const form = useForm<RechargeForm>({
    resolver: zodResolver(rechargeSchema),
    defaultValues: { amount: 0, remark: '' },
  });

  // Input is in yuan (CNY) — multiply by 1,000,000 to get micro-yuan
  const yuanToMicro = (yuan: number): number => Math.round(yuan * MICRO_PER_YUAN);

  const onSubmitRecharge = async (data: RechargeForm) => {
    setIsSubmitting(true);
    try {
      // Convert yuan → micro-yuan before sending to server
      const amountMicro = yuanToMicro(data.amount);
      const res = await createRechargeRequest({ amount: amountMicro, remark: data.remark || '' });
      if (res.data?.success) {
        notify({ type: 'success', message: tr('request.success', 'Recharge request submitted successfully! Awaiting admin approval.') });
        form.reset();
        loadMyRequests();
      } else {
        notify({
          type: 'error',
          message: res.data?.message || tr('request.failed', 'Failed to submit recharge request'),
        });
      }
    } catch (error) {
      notify({
        type: 'error',
        message: error instanceof Error ? error.message : tr('request.failed', 'Failed to submit'),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const statusBadge = (status: number) => {
    switch (status) {
      case 1:
        return <Badge variant="secondary">{tr('history.pending', 'Pending')}</Badge>;
      case 2:
        return <Badge className="bg-success-muted text-success-foreground">{tr('history.approved', 'Approved')}</Badge>;
      case 3:
        return <Badge variant="destructive">{tr('history.rejected', 'Rejected')}</Badge>;
      default:
        return null;
    }
  };

  useEffect(() => {
    loadUserData();
    loadSystemStatus();
    loadMyRequests();
  }, []);

  return (
    <ResponsivePageContainer
      title={tr('title', 'Top Up')}
      description={tr('description', 'Manage your account balance and submit recharge requests')}
      className="max-w-4xl"
    >
      <div className="space-y-6">
        {/* Current Balance */}
        <Card>
          <CardHeader>
            <CardTitle>{tr('balance.title', 'Current Balance')}</CardTitle>
            <CardDescription>{tr('balance.description', 'Your current quota balance')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-center">
              <div className="text-3xl font-bold text-primary mb-2">¥{(userBalance / MICRO_PER_YUAN).toFixed(2)}</div>
              <p className="text-sm text-muted-foreground">{tr('balance.available', 'Available balance (CNY)')}</p>
              <Button variant="outline" className="mt-4" onClick={loadUserData}>
                {tr('balance.refresh', 'Refresh Balance')}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Recharge Request Form */}
        <Card>
          <CardHeader>
            <CardTitle>{tr('request.title', 'Submit Recharge Request')}</CardTitle>
            <CardDescription>{tr('request.description', 'Enter the amount you want to recharge. An admin will review and approve your request.')}</CardDescription>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmitRecharge)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="amount"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tr('request.amount_currency_label', 'Amount (CNY) *')}</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min="0"
                          step="0.01"
                          placeholder={tr('request.amount_placeholder', 'Enter amount in yuan...')}
                          {...field}
                        />
                      </FormControl>
                      {(field.value || 0) > 0 && (
                        <p className="text-xs text-muted-foreground mt-1">
                          ≈ ¥{Number(field.value || 0).toFixed(2)}
                        </p>
                      )}
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="remark"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{tr('request.remark_label', 'Remark (optional)')}</FormLabel>
                      <FormControl>
                        <Textarea placeholder={tr('request.remark_placeholder', 'Any notes for the admin...')} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" className="w-full" disabled={isSubmitting}>
                  {isSubmitting ? tr('request.submitting', 'Submitting...') : tr('request.submit', 'Submit Request')}
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>

        {/* My Recent Requests */}
        {myRequests.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>{tr('history.title', 'My Recharge Requests')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {myRequests.map((req: TopUpRequest) => (
                  <div key={req.id} className="flex items-center justify-between p-3 border rounded-lg">
                    <div className="flex items-center gap-3">
                      {statusBadge(req.status)}
                      <div>
                        <span className="font-mono font-medium">¥{(req.amount / MICRO_PER_YUAN).toFixed(2)}</span>
                        {req.remark && <span className="text-xs text-muted-foreground ml-2">- {req.remark}</span>}
                        {req.admin_remark && (
                          <div className="text-xs text-muted-foreground mt-0.5">
                            Admin: {req.admin_remark}
                          </div>
                        )}
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground hidden sm:inline">
                      {new Date(req.created_time * 1000).toLocaleDateString()}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* External Top-up */}
        {topUpLink && (
          <Card>
            <CardHeader>
              <CardTitle>{tr('online.title', 'Online Payment')}</CardTitle>
              <CardDescription>{tr('online.description', 'Purchase quota through our external payment system')}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center space-y-4">
                <p className="text-sm text-muted-foreground">{tr('online.text', 'Click the button below to open our secure payment portal.')}</p>
                <Button onClick={openTopUpLink} size="lg">
                  {tr('online.button', 'Open Payment Portal')}
                </Button>
                <p className="text-xs text-muted-foreground">{tr('online.note', 'You will be redirected to an external payment system.')}</p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </ResponsivePageContainer>
  );
}

export default TopUpPage;
