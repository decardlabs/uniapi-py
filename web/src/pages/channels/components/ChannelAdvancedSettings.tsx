import type { UseFormReturn } from 'react-hook-form';
import { FormControl, FormField, FormItem, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import type { ChannelForm } from '../schemas';
import { LabelWithHelp } from './LabelWithHelp';

interface ChannelAdvancedSettingsProps {
  form: UseFormReturn<ChannelForm>;
  normalizedChannelType: number | null;
  tr: (key: string, defaultValue: string, options?: Record<string, unknown>) => string;
}

export const ChannelAdvancedSettings = ({ form, tr }: ChannelAdvancedSettingsProps) => {
  const fieldHasError = (name: string) => !!(form.formState.errors as any)?.[name];
  const errorClass = (name: string) => (fieldHasError(name) ? 'border-destructive focus-visible:ring-destructive' : '');

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <FormField
        control={form.control}
        name="priority"
        render={({ field }) => (
          <FormItem>
            <LabelWithHelp
              label={tr('priority.label', 'Priority')}
              help={tr('priority.help', 'Higher priority channels are tried first. Default is 0.')}
            />
            <FormControl>
              <Input type="number" className={errorClass('priority')} {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="weight"
        render={({ field }) => (
          <FormItem>
            <LabelWithHelp
              label={tr('weight.label', 'Weight')}
              help={tr('weight.help', 'Used for load balancing between channels of the same priority. Default is 0.')}
            />
            <FormControl>
              <Input type="number" className={errorClass('weight')} {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name="ratelimit"
        render={({ field }) => (
          <FormItem>
            <LabelWithHelp
              label={tr('ratelimit.label', 'Rate Limit')}
              help={tr('ratelimit.help', 'Maximum requests per minute. 0 means unlimited.')}
            />
            <FormControl>
              <Input type="number" min="0" className={errorClass('ratelimit')} {...field} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <div className="col-span-1 md:col-span-3">
        <FormField
          control={form.control}
          name="system_prompt"
          render={({ field }) => (
            <FormItem>
              <LabelWithHelp
                label={tr('system_prompt.label', 'System Prompt')}
                help={tr('system_prompt.help', 'Force a system prompt for all requests to this channel.')}
              />
              <FormControl>
                <Textarea
                  placeholder={tr('system_prompt.placeholder', 'You are a helpful assistant...')}
                  className={`min-h-[100px] ${errorClass('system_prompt')}`}
                  {...field}
                  value={field.value || ''}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>
    </div>
  );
};
