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
  availableModels: { id: string; name: string }[];
  currentCatalogModels: string[];
  hasCuratedModels: boolean;
  defaultPricing: string;
  notify: (options: any) => void;
  tr: (key: string, defaultValue: string, options?: Record<string, unknown>) => string;
}

export const ChannelModelSettings = ({
  form,
  availableModels,
  currentCatalogModels,
  hasCuratedModels,
  defaultPricing,
  notify,
  tr,
}: ChannelModelSettingsProps) => {
  const FALLBACK_MODEL_CONFIG = {
    ratio: 1,
    completion_ratio: 1,
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
    const currentModels = form.getValues('models');
    const recommendedModelIds = availableModels.map((model) => model.id);
    const uniqueModels = [...new Set([...currentModels, ...recommendedModelIds])];
    form.setValue('models', uniqueModels);
  };

  const clearModels = () => {
    form.setValue('models', []);
  };

  const formatModelMapping = () => {
    const current = form.getValues('model_mapping');
    const selectedModels = form.getValues('models') || [];
    const sourceModels = selectedModels.length > 0 ? selectedModels : currentCatalogModels;

    if (sourceModels.length === 0) {
      const formatted = formatJSON(current);
      form.setValue('model_mapping', formatted);
      return;
    }

    let existingMapping: Record<string, string> = {};
    if (current && current.trim() !== '') {
      try {
        const parsed = JSON.parse(current);
        if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
          existingMapping = Object.entries(parsed as Record<string, unknown>).reduce(
            (acc, [key, value]) => {
              if (typeof value === 'string') {
                acc[key] = value;
              }
              return acc;
            },
            {} as Record<string, string>
          );
        }
      } catch {
        existingMapping = {};
      }
    }

    const deduplicatedModels = [...new Set(sourceModels)];
    deduplicatedModels.forEach((modelName) => {
      if (!Object.prototype.hasOwnProperty.call(existingMapping, modelName)) {
        existingMapping[modelName] = modelName;
      }
    });

    form.setValue('model_mapping', JSON.stringify(existingMapping, null, 2));
  };

  /**
   * formatModelConfigs formats the model_configs JSON for readability and updates the form value.
   * @returns void
   */
  const formatModelConfigs = () => {
    const current = form.getValues('model_configs');
    const formatted = formatJSON(current);
    form.setValue('model_configs', formatted);
  };

  /**
   * loadDefaultModelConfigs applies the default pricing config to the model_configs field.
   * @returns void
   */
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
      <div className="rounded-lg border bg-muted/20 p-3 text-sm text-muted-foreground">
        {hasCuratedModels
          ? tr(
              'models.explainer_curated',
              'This channel type has {{recommendedCount}} recommended model names. If you need the broader upstream list, use "Add Provider Catalog" to import all {{catalogCount}} known model names.',
              {
                recommendedCount: availableModels.length,
                catalogCount: currentCatalogModels.length,
              }
            )
          : tr(
              'models.explainer_catalog',
              'This channel type uses the provider catalog directly. You can import all {{catalogCount}} known model names or add custom names manually.',
              {
                catalogCount: currentCatalogModels.length,
              }
            )}
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {hasCuratedModels && (
          <div className="rounded-lg border bg-background p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="text-sm font-medium">{tr('models.recommended_title', 'Recommended Model Names')}</div>
                <div className="text-sm text-muted-foreground">
                  {tr(
                    'models.recommended_description',
                    'A smaller curated list for common setups. Use this when you want a cleaner starting point.'
                  )}
                </div>
              </div>
              <div className="rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">{availableModels.length}</div>
            </div>
            <div className="mt-3">
              <Button type="button" variant="outline" size="sm" onClick={addRecommendedModels}>
                {tr('models.add_recommended', 'Add Recommended Models ({{count}})', {
                  count: availableModels.length,
                })}
              </Button>
            </div>
          </div>
        )}

        <div className="rounded-lg border bg-background p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="text-sm font-medium">{tr('models.catalog_title', 'Provider Catalog')}</div>
              <div className="text-sm text-muted-foreground">
                {tr(
                  'models.catalog_description',
                  'All model names currently known for this provider type. Import this when you need the full catalog instead of the curated subset.'
                )}
              </div>
            </div>
            <div className="rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">{currentCatalogModels.length}</div>
          </div>
          <div className="mt-3">
            <Button type="button" variant="outline" size="sm" onClick={addCatalogModels}>
              {tr('models.add_catalog', 'Add Provider Catalog ({{count}})', {
                count: currentCatalogModels.length,
              })}
            </Button>
          </div>
        </div>
      </div>

      <FormField
        control={form.control}
        name="models"
        render={() => (
          <FormItem>
            <SelectionListManager
              label={tr('models.label', 'Supported Model Names *')}
              help={
                hasCuratedModels
                  ? tr(
                      'models.help_curated',
                      'These are recommended model names for this channel type. You can add the full provider catalog or custom model names below.'
                    )
                  : tr(
                      'models.help_catalog',
                      'These are known model names for this channel type. You can also add custom model names if your upstream supports them.'
                    )
              }
              options={availableModels.map((model) => ({
                value: model.id,
                label: model.name,
              }))}
              selected={form.watch('models')}
              onChange={(next) => form.setValue('models', next)}
              searchPlaceholder={tr('models.search_placeholder', 'Search models...')}
              customPlaceholder={tr('models.custom_placeholder', 'Add custom model...')}
              addLabel={tr('common.add', 'Add')}
              selectedSummaryLabel={(count) =>
                tr('models.selected_count', 'Enabled Models ({{count}})', {
                  count,
                })
              }
              emptySelectedLabel={tr('models.no_selection', 'No model names selected')}
              noOptionsLabel={tr('models.no_match', 'No model names found')}
              actions={
                <>
                  <Button type="button" variant="outline" onClick={clearModels} className="text-destructive hover:text-destructive">
                    {tr('models.clear', 'Clear Models')}
                  </Button>
                </>
              }
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
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs self-start sm:self-auto"
                  onClick={formatModelMapping}
                >
                  {tr('common.format_json', 'Format JSON')}
                </Button>
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
                      'Optional overrides for ratio, completion_ratio, and max_tokens. This does not control which model names are enabled above.'
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
                  <Button type="button" variant="ghost" size="sm" className="h-6 text-xs" onClick={formatModelConfigs}>
                    {tr('common.format_json', 'Format JSON')}
                  </Button>
                </div>
              </div>
              <FormControl>
                <Textarea
                  placeholder={tr('model_configs.placeholder', '{"provider/actual-model-name": {"ratio": 1, "completion_ratio": 1, "max_tokens": 128000}}', {
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
