import { FormControl, FormField, FormItem, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Lock } from 'lucide-react';
import { type UseFormReturn } from 'react-hook-form';
import { OPENAI_COMPATIBLE_API_FORMAT_OPTIONS } from '../constants';
import type { ChannelForm } from '../schemas';
import { LabelWithHelp } from './LabelWithHelp';

interface ChannelSpecificConfigProps {
  form: UseFormReturn<ChannelForm>;
  normalizedChannelType: number | null;
  defaultBaseURL: string;
  baseURLEditable: boolean;
  tr: (key: string, defaultValue: string, options?: Record<string, unknown>) => string;
}

// Channel types that have their own dedicated base_url field in the channel-specific config
const CHANNEL_TYPES_WITH_INTERNAL_BASE_URL = new Set<number>([50]);

export const ChannelSpecificConfig = ({ form, normalizedChannelType, defaultBaseURL, baseURLEditable, tr }: ChannelSpecificConfigProps) => {
  const fieldHasError = (name: string) => !!(form.formState.errors as any)?.[name];
  const errorClass = (name: string) => (fieldHasError(name) ? 'border-destructive focus-visible:ring-destructive' : '');

  // Common base URL field - shown for all channel types except those with internal base_url
  const showCommonBaseURL = normalizedChannelType !== null && !CHANNEL_TYPES_WITH_INTERNAL_BASE_URL.has(normalizedChannelType);

  const commonBaseURLField = showCommonBaseURL ? (
    <FormField
      control={form.control}
      name="base_url"
      render={({ field }) => (
        <FormItem>
          <div className="flex items-center gap-2">
            <LabelWithHelp
              label={tr('common.base_url.label', 'API Base URL')}
              help={
                baseURLEditable
                  ? tr('common.base_url.help_editable', 'Custom API base URL. Leave empty to use the default URL.')
                  : tr('common.base_url.help_readonly', 'The API base URL for this channel type is fixed and cannot be modified.')
              }
            />
            {!baseURLEditable && <Lock className="h-3 w-3 text-muted-foreground" />}
          </div>
          <FormControl>
            <Input
              placeholder={defaultBaseURL || tr('common.base_url.placeholder', 'https://api.example.com')}
              className={`${errorClass('base_url')} ${!baseURLEditable ? 'bg-muted cursor-not-allowed' : ''}`}
              disabled={!baseURLEditable}
              readOnly={!baseURLEditable}
              {...field}
              value={baseURLEditable ? field.value : defaultBaseURL || field.value}
            />
          </FormControl>
          {!baseURLEditable && defaultBaseURL && (
            <span className="text-xs text-muted-foreground">
              {tr('common.base_url.fixed_note', 'Using default: {{url}}', {
                url: defaultBaseURL,
              })}
            </span>
          )}
          <FormMessage />
        </FormItem>
      )}
    />
  ) : null;

  // Render channel-specific configuration (simplified: only OpenAI Compatible has special config)
  const renderChannelSpecificConfig = () => {
    switch (normalizedChannelType) {
      case 50: // OpenAI Compatible
        return (
          <div className="space-y-4 p-4 border rounded-lg bg-info-muted">
            <h4 className="font-medium text-info-foreground">{tr('openai_compatible.heading', 'OpenAI Compatible Configuration')}</h4>
            <FormField
              control={form.control}
              name="base_url"
              render={({ field }) => (
                <FormItem>
                  <LabelWithHelp
                    label={tr('openai_compatible.base_url.label', 'Base URL *')}
                    help={tr(
                      'openai_compatible.base_url.help',
                      'Base URL of the OpenAI-compatible endpoint, e.g., https://api.your-provider.com. /v1 is appended automatically when required.'
                    )}
                  />
                  <FormControl>
                    <Input
                      placeholder={defaultBaseURL || tr('openai_compatible.base_url.placeholder', 'https://api.your-provider.com')}
                      className={errorClass('base_url')}
                      required
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="config.api_format"
              render={({ field }) => (
                <FormItem>
                  <LabelWithHelp
                    label={tr('openai_compatible.api_format.label', 'Upstream API Format *')}
                    help={tr(
                      'openai_compatible.api_format.help',
                      'Select which upstream API surface should handle requests. ChatCompletion is the historical default; choose Response when the upstream expects OpenAI Response API payloads.'
                    )}
                  />
                  <FormControl>
                    <Select value={field.value ?? 'chat_completion'} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue placeholder={tr('openai_compatible.api_format.placeholder', 'Select upstream API format')} />
                      </SelectTrigger>
                      <SelectContent>
                        {OPENAI_COMPATIBLE_API_FORMAT_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {tr(`openai_compatible.api_format.option.${option.value}`, option.label)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        );

      default:
        return null;
    }
  };

  const channelSpecificConfig = renderChannelSpecificConfig();

  if (!commonBaseURLField && !channelSpecificConfig) {
    return null;
  }

  return (
    <div className="space-y-4">
      {commonBaseURLField}
      {channelSpecificConfig}
    </div>
  );
};
