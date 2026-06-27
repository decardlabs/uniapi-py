import { Button } from '@/components/ui/button';
import { FormControl, FormField, FormItem, FormMessage } from '@/components/ui/form';
import { SelectionListManager } from '@/components/ui/selection-list-manager';
import { Textarea } from '@/components/ui/textarea';
import type { UseFormReturn } from 'react-hook-form';
import { MODEL_CONFIGS_EXAMPLE, MODEL_MAPPING_EXAMPLE } from '../constants';
import { formatJSON } from '../helpers';
import type { ChannelForm } from '../schemas';
import { LabelWithHelp } from './LabelWithHelp';

interface ChannelModelSettingsProps {
  form: UseFormReturn<ChannelForm>;
  availableModels?: { id: string; name: string }[];
  currentCatalogModels: string[];
  hasCuratedModels?: boolean;
  defaultPricing: string;
  notify: (options: any) => void;
  tr: (key: string, defaultValue: string, options?: Record<string, unknown>) => string;
}

export const ChannelModelSettings = ({
  form,
  availableModels = [],
  currentCatalogModels,
  hasCuratedModels = false,
  defaultPricing,
  notify,
  tr,
}: ChannelModelSettingsProps) => {
  const FALLBACK_MODEL_CONFIG = {
    input_price: 1.0,
    output_price: 2.0,
    cache_hit_price: 0.02,
    max_tokens: 128000,
  };

  const fieldHasError = (name: string) => !!(form.formState.errors as any)?.[name];
  const errorClass = (name: string) => (fieldHasError(name) ? 'border-destructive focus-visible:ring-destructive' : '');

  const addCatalogModels = () => {
    if (currentCatalogModels.length === 0) {
      return;
    }
    const currentModels = form.getValues('models');
    const uniqueModels = [...new Set([...currentModels, ...currentCatalogModels])];
    form.setValue('models', uniqueModels);
  };

  const addRecommendedModels = () => {
    if (availableModels.length === 0) {
      return;
    }
    const currentModels = form.getValues('models');
    const modelIds = availableModels.map((m) => m.id);
    const uniqueModels = [...new Set([...currentModels, ...modelIds])];
    form.setValue('models', uniqueModels);
  };

  const generateModelMapping = () => {
    const selectedModels = form.getValues('models') || [];
    const sourceModels = selectedModels.length > 0 ? selectedModels : currentCatalogModels;
    if (sourceModels.length === 0) return;
    const existingMappingStr = form.getValues('model_mapping') || '';
    let existingMapping: Record<string, string> = {};
    try {
      if (existingMappingStr.trim()) {
        const parsed = JSON.parse(existingMappingStr) as Record<string, unknown>;
        if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
          for (const [k, v] of Object.entries(parsed)) {
            if (typeof v === 'string') existingMapping[k] = v;
          }
        }
      }
    } catch {
      // Ignore malformed existing mapping and fall back to one-to-one.
    }
    const mapping: Record<string, string> = {};
    [...new Set(sourceModels)].forEach((model) => { mapping[model] = existingMapping[model] ?? model; });
    form.setValue('model_mapping', JSON.stringify(mapping, null, 2));
  };

  const loadDefaultModelConfigs = () => {
    console.debug('[ChannelModelSettings] Load default model configs', {
      hasDefaultPricing: Boolean(defaultPricing),
    });
    const selectedModels = form.getValues('models') || [];
    const sourceModels = selectedModels.length > 0 ? selectedModels : currentCatalogModels;
    if (sourceModels.length === 0) {
      if (defaultPricing) {
        form.setValue('model_configs', formatJSON(defaultPricing));
      }
      return;
    }

    const parsedDefaults: Record<string, unknown> = {};
    try {
      if (defaultPricing && defaultPricing.trim() !== '') {
        const parsed = JSON.parse(defaultPricing) as Record<string, unknown>;
        if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
          Object.assign(parsedDefaults, parsed);
        }
      }
    } catch {
      // Ignore malformed provider defaults and fall back to generated defaults.
    }

    const mergedConfigs: Record<string, unknown> = {};
    let hasProviderDefaults = false;
    [...new Set(sourceModels)].forEach((modelName) => {
      const providerValue = parsedDefaults[modelName];
      if (providerValue && typeof providerValue === 'object' && !Array.isArray(providerValue)) {
        mergedConfigs[modelName] = providerValue;
        hasProviderDefaults = true;
      } else {
        mergedConfigs[modelName] = { ...FALLBACK_MODEL_CONFIG };
      }
    });

    if (!hasProviderDefaults) {
      notify({
        type: 'warning',
        title: tr('model_configs.no_defaults_title', 'No matching defaults'),
        message: tr(
          'model_configs.no_defaults_message',
          'No provider default pricing was found for the currently selected models.'
        ),
      });
    }

    form.setValue('model_configs', JSON.stringify(mergedConfigs, null, 2));
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border bg-background p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="text-sm font-medium">{tr('models.catalog_title', 'Provider Catalog')}</div>
            <div className="text-sm text-muted-foreground">
              {tr('models.catalog_description', 'Available model names for this provider type. Add or customise below.')}
            </div>
          </div>
          <div className="rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">{currentCatalogModels.length}</div>
        </div>
        <div className="mt-3">
          {hasCuratedModels && availableModels.length > 0 && (
            <Button type="button" variant="outline" size="sm" onClick={addRecommendedModels} className="mr-2">
              {tr('models.add_recommended', 'Add Recommended Models ({{count}})', {
                count: availableModels.length,
              })}
            </Button>
          )}
          <Button type="button" variant="outline" size="sm" onClick={addCatalogModels}>
            {tr('models.add_catalog', 'Add Provider Catalog ({{count}})', {
              count: currentCatalogModels.length,
            })}
          </Button>
        </div>
      </div>

      <FormField
        control={form.control}
        name="models"
        render={() => (
          <FormItem>
            <SelectionListManager
              label=""
              options={[]}
              selected={form.watch('models')}
              onChange={(next) => form.setValue('models', next)}
              customPlaceholder={tr('models.custom_placeholder', 'Add custom model...')}
              addLabel={tr('common.add', 'Add')}
              selectedSummaryLabel={(count) =>
                tr('models.selected_count', 'Enabled Models ({{count}})', { count })
              }
              emptySelectedLabel={tr('models.no_selection', 'No model names selected')}
              noOptionsLabel={tr('models.no_match', 'No model names found')}
            />
            <FormMessage />
          </FormItem>
        )}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <FormField
          control={form.control}
          name="model_mapping"
          render={({ field }) => (
            <FormItem>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <LabelWithHelp
                  label={tr('model_mapping.label', 'Request Model Mapping (JSON)')}
                  help={
                    tr(
                      'model_mapping.help',
                      'Optional. Only use this when the client-facing model name should be translated to a different upstream model name.'
                    )
                  }
                />
                <div className="flex flex-wrap gap-2 self-start sm:self-auto">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs"
                    onClick={generateModelMapping}
                  >
                    {tr('model_mapping.generate', 'Format JSON')}
                  </Button>
                </div>
              </div>
              <FormControl>
                <Textarea
                  placeholder={tr('model_mapping.placeholder', '{"client-facing-model": "provider/actual-model-name"}', {
                    example: JSON.stringify(MODEL_MAPPING_EXAMPLE, null, 2),
                  })}
                  className={`font-mono text-xs min-h-[150px] ${errorClass('model_mapping')}`}
                  {...field}
                  value={field.value || ''}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="model_configs"
          render={({ field }) => (
            <FormItem>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <LabelWithHelp
                  label={tr('model_configs.label', 'Per-Model Pricing & Limits (JSON)')}
                  help={
                    tr(
                      'model_configs.help',
                      'Optional overrides for input_price (¥/M tokens), cache_hit_price, output_price, and max_tokens. Uses global pricing when not set. Old format ratio/completion_ratio also accepted.'
                    )
                  }
                />
                <div className="flex flex-wrap gap-2 self-start sm:self-auto">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 text-xs"
                    onClick={loadDefaultModelConfigs}
                  >
                    {tr('model_configs.load_default', 'Load Provider Defaults')}
                  </Button>
                </div>
              </div>
              <FormControl>
                <Textarea
                  placeholder={tr('model_configs.placeholder', '{"model-name": {"input_price": 1.0, "output_price": 2.0, "cache_hit_price": 0.02, "max_tokens": 128000}}', {
                    example: JSON.stringify(MODEL_CONFIGS_EXAMPLE, null, 2),
                  })}
                  className={`font-mono text-xs min-h-[150px] ${errorClass('model_configs')}`}
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
