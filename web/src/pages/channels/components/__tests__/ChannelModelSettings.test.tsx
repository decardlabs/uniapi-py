import { fireEvent, render, screen } from '@testing-library/react';
import { useEffect } from 'react';
import { useForm, type UseFormReturn } from 'react-hook-form';
import { describe, expect, it, vi } from 'vitest';

import { TooltipProvider } from '@/components/ui/tooltip';
import type { ChannelForm } from '../../schemas';
import { ChannelModelSettings } from '../ChannelModelSettings';

/**
 * tr returns the default translation value for test rendering.
 * @param _key - i18n key (unused in tests).
 * @param defaultValue - fallback string to render.
 * @returns The fallback translation value.
 */
const tr = (_key: string, defaultValue: string, options?: Record<string, unknown>) => {
  if (!options) {
    return defaultValue;
  }

  return Object.entries(options).reduce((text, [name, value]) => text.replace(`{{${name}}}`, String(value)), defaultValue);
};

const baseDefaults: ChannelForm = {
  name: 'Test Channel',
  type: 1,
  key: '',
  base_url: '',
  other: {},
  models: [],
  model_mapping: '',
  model_configs: '',
  tooling: '',
  system_prompt: '',
  groups: ['default'],
  priority: 0,
  weight: 0,
  ratelimit: 0,
  config: {
    region: '',
    ak: '',
    sk: '',
    user_id: '',
    vertex_ai_project_id: '',
    vertex_ai_adc: '',
    auth_type: 'personal_access_token',
    api_format: 'chat_completion',
    supported_endpoints: [],
    mcp_tool_blacklist: [],
  },
  inference_profile_arn_map: '',
};

/**
 * TestHarnessProps defines inputs for the test harness component.
 */
interface TestHarnessProps {
  availableModels?: { id: string; name: string }[];
  currentCatalogModels?: string[];
  hasCuratedModels?: boolean;
  defaultPricing: string;
  notify?: (options: any) => void;
  onReady: (form: UseFormReturn<ChannelForm>) => void;
}

/**
 * TestHarness wires react-hook-form into ChannelModelSettings for testing.
 * @param defaultPricing - the default pricing string to inject.
 * @param onReady - callback to expose the form instance.
 * @returns The rendered ChannelModelSettings component.
 */
const TestHarness = ({
  availableModels = [],
  currentCatalogModels = [],
  hasCuratedModels = false,
  defaultPricing,
  notify = vi.fn(),
  onReady,
}: TestHarnessProps) => {
  const form = useForm<ChannelForm>({ defaultValues: baseDefaults });

  useEffect(() => {
    onReady(form);
  }, [form, onReady]);

  return (
    <TooltipProvider>
      <ChannelModelSettings
        form={form}
        currentCatalogModels={currentCatalogModels}
        defaultPricing={defaultPricing}
        notify={notify}
        tr={tr}
      />
    </TooltipProvider>
  );
};

describe('ChannelModelSettings', () => {
  it('loads default model configs into the form', () => {
    let formRef: UseFormReturn<ChannelForm> | null = null;

    render(
      <TestHarness
        defaultPricing='{"gpt-4": {"ratio": 1}}'
        onReady={(form) => {
          formRef = form;
        }}
      />
    );

    const button = screen.getByRole('button', { name: 'Load Provider Defaults' });
    fireEvent.click(button);

    expect(formRef?.getValues('model_configs')).toBe('{\n  "gpt-4": {\n    "ratio": 1\n  }\n}');
  });

  it('loads default model configs filtered by selected models', () => {
    let formRef: UseFormReturn<ChannelForm> | null = null;

    render(
      <TestHarness
        defaultPricing='{"gpt-4": {"ratio": 1}, "deepseek-chat": {"ratio": 0.14}, "unused": {"ratio": 999}}'
        onReady={(form) => {
          formRef = form;
        }}
      />
    );

    formRef?.setValue('models', ['deepseek-chat', 'gpt-4']);
    fireEvent.click(screen.getByRole('button', { name: 'Load Provider Defaults' }));

    expect(formRef?.getValues('model_configs')).toBe(
      '{\n  "deepseek-chat": {\n    "ratio": 0.14\n  },\n  "gpt-4": {\n    "ratio": 1\n  }\n}'
    );
  });

  it('generates fallback model configs when provider defaults are missing', () => {
    let formRef: UseFormReturn<ChannelForm> | null = null;

    render(
      <TestHarness
        defaultPricing=''
        currentCatalogModels={['gpt-4', 'deepseek-chat']}
        onReady={(form) => {
          formRef = form;
        }}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Load Provider Defaults' }));

    expect(formRef?.getValues('model_configs')).toBe(
      '{\n  "gpt-4": {\n    "input_price": 1,\n    "output_price": 2,\n    "cache_hit_price": 0.02,\n    "max_tokens": 128000\n  },\n  "deepseek-chat": {\n    "input_price": 1,\n    "output_price": 2,\n    "cache_hit_price": 0.02,\n    "max_tokens": 128000\n  }\n}'
    );
  });

  it('adds recommended and catalog models from separate actions', () => {
    let formRef: UseFormReturn<ChannelForm> | null = null;

    render(
      <TestHarness
        availableModels={[
          { id: 'recommended-a', name: 'recommended-a' },
          { id: 'recommended-b', name: 'recommended-b' },
        ]}
        currentCatalogModels={['recommended-a', 'catalog-only']}
        hasCuratedModels={true}
        defaultPricing=''
        onReady={(form) => {
          formRef = form;
        }}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Add Recommended Models (2)' }));
    expect(formRef?.getValues('models')).toEqual(['recommended-a', 'recommended-b']);

    fireEvent.click(screen.getByRole('button', { name: 'Add Provider Catalog (2)' }));
    expect(formRef?.getValues('models')).toEqual(['recommended-a', 'recommended-b', 'catalog-only']);
  });

  it('warns and applies fallback defaults when no selected models match provider defaults', () => {
    const notify = vi.fn();
    let formRef: UseFormReturn<ChannelForm> | null = null;

    render(
      <TestHarness
        defaultPricing='{"gpt-4": {"ratio": 1}}'
        notify={notify}
        onReady={(form) => {
          formRef = form;
        }}
      />
    );

    formRef?.setValue('models', ['deepseek-chat']);
    formRef?.setValue('model_configs', '{"existing": {"ratio": 9}}');
    fireEvent.click(screen.getByRole('button', { name: 'Load Provider Defaults' }));

    expect(formRef?.getValues('model_configs')).toBe(
      '{\n  "deepseek-chat": {\n    "input_price": 1,\n    "output_price": 2,\n    "cache_hit_price": 0.02,\n    "max_tokens": 128000\n  }\n}'
    );
    expect(notify).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'warning',
      })
    );
  });

  it('formats model mapping by auto-filling one-to-one mappings for models', () => {
    let formRef: UseFormReturn<ChannelForm> | null = null;

    render(
      <TestHarness
        defaultPricing=''
        currentCatalogModels={['gpt-4', 'deepseek-chat']}
        onReady={(form) => {
          formRef = form;
        }}
      />
    );

    formRef?.setValue('models', ['gpt-4', 'deepseek-chat']);
    formRef?.setValue('model_mapping', '{"gpt-4": "openai/gpt-4"}');
    fireEvent.click(screen.getAllByRole('button', { name: 'Format JSON' })[0]);

    expect(formRef?.getValues('model_mapping')).toBe(
      '{\n  "gpt-4": "openai/gpt-4",\n  "deepseek-chat": "deepseek-chat"\n}'
    );
  });
});
