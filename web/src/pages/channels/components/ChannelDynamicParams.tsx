import { FormField, FormItem, FormControl, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { LabelWithHelp } from './LabelWithHelp';
import type { UseFormReturn } from 'react-hook-form';
import type { ChannelForm } from '../schemas';

export interface ChannelTypeTemplateField {
  key: string;
  label: string;
  type: 'string' | 'number' | 'boolean' | 'select' | 'textarea';
  required?: boolean;
  help?: string;
  options?: { value: string | number; label: string }[];
  default?: string | number | boolean;
}

export interface ChannelTypeTemplate {
  fields: ChannelTypeTemplateField[];
  group?: string;
}

export interface ChannelDynamicParamsProps {
  form: UseFormReturn<ChannelForm>;
  template: ChannelTypeTemplate | null;
  tr: (key: string, defaultValue: string, options?: Record<string, unknown>) => string;
}

import { useState } from 'react';

// 支持字段分组，group 字段为数组 [{ name, fields: [...] }]
type GroupedTemplate = { name: string; fields: ChannelTypeTemplateField[] }[];

function groupFields(fields: ChannelTypeTemplateField[]): GroupedTemplate {
  const groups: Record<string, ChannelTypeTemplateField[]> = {};
  for (const field of fields) {
    const group = (field as any).group || 'Basic';
    if (!groups[group]) groups[group] = [];
    groups[group].push(field);
  }
  return Object.entries(groups).map(([name, fields]) => ({ name, fields }));
}

export function ChannelDynamicParams({ form, template, tr }: ChannelDynamicParamsProps) {
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  if (!template || !template.fields.length) return null;
  const grouped = groupFields(template.fields);
  return (
    <div className="space-y-6">
      {grouped.map(({ name, fields }) => (
        <div key={name} className="border rounded-md">
          <div
            className="flex items-center justify-between px-3 py-2 bg-muted cursor-pointer select-none"
            onClick={() => setOpenGroups((prev) => ({ ...prev, [name]: !prev[name] }))}
          >
            <span className="font-semibold text-base">{tr(`template.group.${name}`, name)}</span>
            <span>{openGroups[name] !== false ? '▼' : '▶'}</span>
          </div>
          {openGroups[name] !== false && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-3">
              {fields.map((field) => {
                const inputId = `channel-param-${field.key}`;
                return (
                  <FormField
                    key={field.key}
                    control={form.control}
                    name={`other.${field.key}` as const}
                    render={({ field: rhfField }) => (
                      <FormItem>
                        <LabelWithHelp
                          label={tr(`template.${field.key}.label`, field.label)}
                          help={field.help ? tr(`template.${field.key}.help`, field.help) : undefined}
                          htmlFor={inputId}
                        />
                        <FormControl>
                          {field.type === 'string' && (
                            <Input {...rhfField} placeholder={field.label} id={inputId} />
                          )}
                          {field.type === 'number' && (
                            <Input type="number" {...rhfField} placeholder={field.label} id={inputId} />
                          )}
                          {field.type === 'textarea' && (
                            <Textarea {...rhfField} placeholder={field.label} id={inputId} />
                          )}
                          {field.type === 'boolean' && (
                            <Checkbox checked={!!rhfField.value} onCheckedChange={rhfField.onChange} aria-label={field.label} id={inputId} />
                          )}
                          {field.type === 'select' && field.options && (
                            <Select value={rhfField.value} onValueChange={rhfField.onChange}>
                              <SelectTrigger id={inputId}>
                                <SelectValue placeholder={field.label} />
                              </SelectTrigger>
                              <SelectContent>
                                {field.options.map((opt) => (
                                  <SelectItem key={opt.value} value={String(opt.value)}>
                                    {opt.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          )}
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
