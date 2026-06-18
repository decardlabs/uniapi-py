import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useForm, FormProvider } from 'react-hook-form';
import { ChannelDynamicParams, ChannelTypeTemplate } from './ChannelDynamicParams';
import { TooltipProvider } from '@/components/ui/tooltip';

const template: ChannelTypeTemplate = {
  fields: [
    { key: 'api_key', label: 'API Key', type: 'string', required: true, help: 'The API key for authentication.' },
    { key: 'region', label: 'Region', type: 'string', required: false },
    { key: 'enabled', label: 'Enabled', type: 'boolean', required: false },
    { key: 'mode', label: 'Mode', type: 'select', options: [ { value: 'a', label: 'A' }, { value: 'b', label: 'B' } ] },
    { key: 'desc', label: 'Description', type: 'textarea' }
  ]
};

const tr = (k: string, d: string) => d;



import { type ChannelForm } from '../schemas';
function renderWithForm(template: ChannelTypeTemplate, tr: (k: string, d: string) => string) {
  function Wrapper() {
    const defaultValues: ChannelForm = {
      name: '',
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
    const methods = useForm<ChannelForm>({ defaultValues });
    return (
      <TooltipProvider>
        <FormProvider {...methods}>
          <ChannelDynamicParams form={methods} template={template} tr={tr} />
        </FormProvider>
      </TooltipProvider>
    );
  }
  return render(<Wrapper />);
}

describe('ChannelDynamicParams', () => {
  it('renders all template fields', () => {
    renderWithForm(template, tr);
    expect(screen.getByLabelText('API Key')).toBeInTheDocument();
    expect(screen.getByLabelText('Region')).toBeInTheDocument();
    expect(screen.getByLabelText('Enabled')).toBeInTheDocument();
    expect(screen.getByLabelText('Mode')).toBeInTheDocument();
    expect(screen.getByLabelText('Description')).toBeInTheDocument();
  });
});
