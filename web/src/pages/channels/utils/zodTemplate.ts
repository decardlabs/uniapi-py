import * as z from 'zod';

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

/**
 * 根据参数模板生成 Zod 校验 schema
 */
export function zodSchemaFromTemplate(template: ChannelTypeTemplate | null) {
  if (!template) return z.object({});
  const shape: Record<string, any> = {};
  for (const field of template.fields) {
    let base: z.ZodTypeAny;
    switch (field.type) {
      case 'string':
      case 'textarea':
        base = z.string();
        break;
      case 'number':
        base = z.coerce.number();
        break;
      case 'boolean':
        base = z.boolean();
        break;
      case 'select':
        if (field.options && field.options.length >= 2) {
          const literals = field.options.map(opt => typeof opt.value === 'number' ? z.literal(opt.value) : z.literal(String(opt.value)));
          if (literals.length >= 2) {
            base = z.union(literals as unknown as [z.ZodTypeAny, z.ZodTypeAny]);
          } else {
            base = z.string();
          }
        } else {
          base = z.string();
        }
        break;
      default:
        base = z.any();
    }
    if (field.required) {
      base = base.refine(v => v !== undefined && v !== null && v !== '', `${field.label} is required`);
    } else {
      base = base.optional();
    }
    shape[field.key] = base;
  }
  return z.object(shape);
}
